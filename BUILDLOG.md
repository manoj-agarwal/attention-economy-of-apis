# Build Log

## 2026-08-09: Initial crawl + token counting (70 servers)

### Collection
- Registry: `registry.modelcontextprotocol.io/v0/servers`, 250 entries requested
- Result: 70 collected, 111 failed, 69 skipped (no remote endpoint)
- Dominant failure: HTTP 401 Unauthorized (85/111) — servers requiring auth
- Crawler patched mid-session: added retry on transient errors (ConnectionError,
  503, Timeout) and lenient JSON-RPC id matching (str/int coercion)

### Token counting
- Method: `tiktoken:o200k_base` (all rows quotable)
- Median tool count: 6.5
- Median catalog cost: 1,776 tokens
- 90th percentile: 7,585 tokens

### Data quality flags
1. **dreamlit outlier**: 42,863 tokens for only 11 tools (~3,900 tok/tool).
   Every tool description is 10k+ chars — likely embedding full API docs in the
   description field rather than a concise summary. Legitimate but extreme.
2. **Near-duplicate registrations**: `auteng/docs` and `auteng/mcp` serve
   identical 7-tool catalogs from different URL paths. The three `child*`
   servers (childadhd, childanxiety, childpsychiatry) have identical tool
   counts and token costs (629 tokens, 6 tools) with near-identical content.
   `dablock` and `dabyte` are also near-clones (5 tools, ~2,370 tokens).
3. **Zero descriptions**: 11 servers (16%) have 0% of parameters described.
4. **borealhost mega-catalog**: 144 tools / 26,711 tokens — largest tool count
   by far, no descriptions on any parameter.

## 2026-08-09: PulseMCP popularity-based crawl (96 servers)

### Source change
- Switched from MCP registry to PulseMCP v0beta API (`api.pulsemcp.com`)
- Sorted ~12k servers by `github_stars` descending, attempted top 250
- Stars range: 74,683 → 4 for the top 250 with remote endpoints
- Page size capped at 200 (API rejects larger); 410 responses handled with retry

### Collection
- Result: 96 collected, 154 failed, 0 skipped
- Dominant failure: HTTPError (142/154) — popular servers tend to require auth
- 4 cross-source duplicates removed (Drillr, BuyWhere, Tandem, auteng/docs)
- 1 file skipped by token counter (FapiaAPI: no tools array)

### Token counting (combined: 162 servers)
- Method: `tiktoken:o200k_base` (all rows quotable)
- Median tool count: 7.0
- Median catalog cost: 1,879 tokens
- 90th percentile: 13,488 tokens

### New data quality flags
1. **Metagraphed mega-outlier**: 300,631 tokens for 230 tools (~1,307 tok/tool).
   Dominates the histogram — 7x the next-largest catalog.
2. **Agentic Mermaid / OptionsAhoy**: 44k and 34k tokens for 9 and 8 tools
   respectively (~4,900 and ~4,300 tok/tool). Same pattern as dreamlit —
   embedding full docs in tool descriptions.
3. Popular servers (high github_stars) have higher auth-gate rate than the
   registry sample — 62% failure vs 44% previously.

## 2026-08-14: weekend2-demo plumbing shakedown (mock only, agent block)

### What ran
- Environment: Python 3.9.6. No live API calls, no `ANTHROPIC_API_KEY` used,
  no `--all` grid. Mock only, so there are **no measurement numbers from this
  block** — MockClient emits synthetic token counts and its verdicts are
  meaningless by design.
- All 12 combinations (variants a/b x tasks 1-6) complete the agent loop in
  `--mock` without error. No 3.9 syntax problems in any module.
- Verification ran from a scratch dir with `harness.TRANSCRIPT_DIR` redirected,
  so `weekend2-demo/transcripts/` was never created. Scratch dir deleted after.

### Changed (in-lane)
- `harness.py`: transcript path was CWD-relative (`Path("transcripts")`), so the
  invocation documented in AGENTS.md (`python weekend2-demo/harness.py`) would
  have written evidence into the repo root instead of the demo folder. Now
  anchored to the script dir via `TRANSCRIPT_DIR`. Per-turn write also moved to
  a context manager. No effect on world state, seeds, or results.

### Verified
- `tasks.py` satisfies the contract `harness.py` expects: `TASKS` keyed by ints
  1-6, each with `prompt`, `failure_switch`, callable `check(world)` (plus an
  unused `note`). Task 5 is the only `failure_switch: True`; task 3 is marked
  the hero task. Matches the README.
- Checks 2-6 correctly return False on an untouched world (not vacuous).
  Task 1's check is a literal `lambda w: True` — it reports SUCCESS regardless
  of behaviour, so the summary table's task-1 row carries no information.

### Failed / blocking (nothing applied — all propose-first)
1. **Surface B cannot complete 5 of 6 tasks even with ideal play.** Verified by
   calling `surface_b.dispatch` directly and evaluating each `check`:
   only task 1 passes; tasks 2, 3, 4, 5, 6 fail.
2. **Root cause A — empty working-hour intersection.** `_candidates()` requires
   every attendee's local hour in [9,17). LA n London = 0 slots and
   LA n Kolkata = 0 slots, so any task with Priya or Elena is unschedulable by
   B. Kills tasks 2, 3, 5 — including the hero clip.
3. **Root cause B — truncate-before-filter.** `_candidates()` returns at most 3
   slots, and `reschedule_meeting` filters for `c > event.start` afterwards, so
   the earlier candidates are consumed and nothing survives. Kills task 4.
4. **Root cause C — world seeding shifts western timezones a day early.**
   Seeding does `day.astimezone(tz).replace(hour=...)` against a UTC-midnight
   anchor, so LA/NY people land on the previous local day: 'you', 'marcus' and
   'sam' hold Sunday meetings and 'you' has **zero** Friday meetings. Task 6
   therefore has nothing to cancel; its `all(...)` clause is vacuously true and
   the check collapses to "did any notification get sent".
5. **Asymmetric success standard.** Surface A passes task 3 by creating the
   event at 00:00 UTC (17:00 PT / 01:00 London / 05:30 Kolkata) — the checks
   never require the meeting to fall in anyone's working hours. B refuses such
   slots by design and is scored as failing. The criteria currently reward A's
   laxity and punish B's rigor.

### Fairness read on the task set
- Every one of the 6 tasks is satisfiable by exactly one Surface B tool call
  (1 -> get_schedule_summary, 2/3/5 -> schedule_meeting, 4 -> reschedule_meeting,
  6 -> cancel_meetings). `find_meeting_time` and `block_focus_time` are never
  needed. The task set is drawn on B's tool boundaries, which is the structural
  rig the fairness doctrine warns about — flagged, not edited.
- Note the two findings point opposite ways: the design favours B, while the
  implementation bugs make B lose badly. Both need the human's decision.

## 2026-08-14: weekend2-demo task redesign against human rulings (mock only)

### Applied
- `surface_b.py` (the only surface change authorised): `_candidates()` gains
  `after=None` and skips slots at or before it; `reschedule_meeting` now calls
  `_candidates(..., after=e["start"])` instead of filtering after truncation.
  Fixes task 4. `surface_a.py` and `calendar_world.py` were not touched.
- `tasks.py` rewritten to 8 tasks:
  - Scheduling casts moved off Priya/Elena onto you/Marcus/Sam. Forced, not
    preferred — see below.
  - New `_humane(event)` predicate: every attendee must see the meeting inside
    their own 9-17 local day. Applied to the checks for tasks 2, 3, 4, 5, 7.
  - Task 7 (new): 45-min sync with Marcus and Sam **plus** a 2-hour focus block.
    Needs two Surface B tools.
  - Task 8 (new): cancel the Sam 1:1 and notify. Cheap for A (4 calls); B must
    locate the day first, so it needs two tools.
  - Tasks 1 and 6 left byte-identical per human ruling.

### Measured: why the hero cast is Marcus+Sam, not Marcus+Priya
Swept every cast through `surface_b.schedule_meeting` at 60 min. With the 9-17
band left unchanged (the band widening was NOT approved), only three casts are
schedulable at all: you+marcus, you+sam, you+marcus+sam. **Every** cast
containing Priya or Elena returns `no_slot`. Dropping Kolkata alone was not
enough; London had to go too. The hero task is therefore 3 people across 2
timezones (LA/NY), not 4 across 4.

### Verified (perfect-play simulation, direct dispatch, no model)
| task | A pass | A calls | B pass | B calls | B tools |
|---|---|---|---|---|---|
| 1 | yes | 2 | yes | 1 | get_schedule_summary |
| 2 | yes | 6 | yes | 1 | schedule_meeting |
| 3 | yes | 13 | yes | 1 | schedule_meeting |
| 4 | yes | 5 | yes | 1 | reschedule_meeting |
| 5 | yes | 14 | yes | 1 | schedule_meeting |
| 6 | NO | 1 | NO | 1 | cancel_meetings |
| 7 | yes | 11 | yes | 2 | schedule_meeting + block_focus_time |
| 8 | yes | 4 | yes | 2 | get_schedule_summary + cancel_meetings |

- 7 of 8 tasks are passable by BOTH surfaces. The humane-hours checks did not
  invert the rig: Surface A still succeeds through competent use of its own 28
  tools, including the 503 retry on task 5 (14 calls vs 13 on task 3).
- All 16 `--variant/--task --mock` combinations run through the real argparse
  path with no exceptions, Python 3.9.6. Transcripts redirected to a scratch
  dir; `weekend2-demo/transcripts/` was never created. Scratch deleted.
- No live API calls. **No token or verdict measurements exist for this block** —
  the A/B call counts above are simulation counts, not model behaviour.

### Failed / still broken
1. **Task 6 is unpassable by both surfaces** under competent play, because both
   repairs were declined. 'you' has no Friday meetings, so the cancellation
   clause is vacuous and only `len(notifications) > 0` bites; B's
   `cancel_meetings("friday")` cancels 0 and notifies 0, and a competent A finds
   nothing to cancel. Correction to the earlier characterisation: the row does
   not print SUCCESS unconditionally — it prints SUCCESS only if the agent sends
   some unrelated notification, which is arguably worse, since a pass would be
   noise rather than evidence.
2. **Task 1 remains uninformative**: `lambda w: True` prints SUCCESS for both
   surfaces regardless of behaviour (human ruling: keep).
3. **`find_meeting_time` is still never exercised.** It cannot be forced by any
   outcome-checked task: it mutates no world state, and `schedule_meeting`
   subsumes it. Would need either a transcript-based check or a surface change,
   neither of which is in scope.
4. Priya and Elena now appear in no scheduling task, so 3 of the 5 seeded people
   and the two most dramatic timezone gaps are unused by the measured set.
5. The grid is now 8x2, not 6x2. The live run will cost roughly a third more
   than the README's estimate.

## 2026-08-14: First commit of weekend2-demo + guardrails (agent block)

### Applied
- Commit `e4c2579` on `main`: 13 files, 1110 insertions. weekend2-demo
  (calendar_world, surface_a, surface_b, harness, tasks, README), AGENTS.md,
  `.cursor/rules/` (data-handling, demo-fairness), TokenCost.png, ToosCount.png,
  a `.gitignore` for macOS/Python junk, and this BUILDLOG.

### Verified
- Staged exactly the 13 intended paths. `git status --porcelain` before the
  commit showed no `.DS_Store` (root and `.cursor/` copies now ignored) and
  nothing under `data/raw/`.
- Working tree clean after the commit, apart from this entry, which is left
  uncommitted for human review.
- Not pushed. The repo has no `origin` remote and `gh` was not invoked.

### Failed / open
- Nothing failed in this block. Still no live API runs, so nothing in this
  commit carries measured token numbers.

## 2026-08-14: Live hero-task measurement ATTEMPTED — aborted, no numbers (agent block)

### Attempted
The authorized live run of the hero task (task 3) on both surfaces, from
`weekend2-demo/`, Python 3.9.6, `anthropic` 0.122.0:

    python3 harness.py --variant a --task 3   # invoked; aborted before first API call
    python3 harness.py --variant b --task 3   # NEVER invoked (see below)

Model: none was contacted. `--model` was not passed, so the harness default
`claude-sonnet-4-6` (`harness.py` MODEL_DEFAULT, line 20) would have been used,
but no request reached the API, so even the model string is unverified here.

### Result: no measured numbers exist for this block
Variant A raised `TypeError: "Could not resolve authentication method..."` from
`anthropic/_client.py::_validate_headers`; the SDK found no credential in this
shell's environment. The traceback terminates inside `_build_request`, before
any HTTP request is sent. Therefore:

- Zero tokens billed, zero turns, zero tool calls, no SUCCESS/FAIL verdict.
  There is no A:B token ratio, because a ratio needs two totals and we have none.
- Intended design was n=1 per variant; achieved n=0 per variant.
- `transcripts/` was created (harness.py line 83, which runs before the turn
  loop) but is EMPTY — 0 files. `tpath` is only written once a response arrives,
  and none did. The empty directory is left in place, not deleted.
- Per the human's standing instruction: credentials were not inspected, no shell
  profile or config file was searched, and the failing run was not retried.
  Variant B was deliberately not invoked — it fails identically at the same line
  and yields no measurement, and the instruction on an auth failure is to stop.

### The one figure that printed, and why it is not quotable
    [meter] cover charge: 28 tools, ~2,051 tokens (est)

Code path for this derived figure (per `.cursor/rules/data-handling.mdc`):
`harness.py` line 66 serializes `surface_a.TOOLS` via
`json.dumps(..., separators=(",",":"), sort_keys=True)`; line 69 passes that
string to `est_tokens()` (line 24), which is `max(1, round(len(s) / 3.5))` — a
character heuristic, not a tokenizer. An estimate must never feed a headline
statistic, so 2,051 is a display number only. The `28 tools` count is exact
(`len(surface_a.TOOLS)`). Surface B's cover-charge line was never printed,
because variant B was never run.

### Environment change, outside the repo
- `python3 -m pip install --user anthropic` (sanctioned by AGENTS.md, and
  human-approved at the prompt): installed anthropic 0.122.0 plus 16 deps into
  `~/Library/Python/3.9/`. An in-workspace virtualenv was attempted first and
  refused by the sandbox.
- No source file was modified. Seed 1776, world, surfaces, and tasks untouched.
  `git status --short` showed only ` M BUILDLOG.md` from a concurrent agent's
  uncommitted edit, which was left alone.

### Failed / open
- The first real measurement is still outstanding. The human holds the key; the
  two commands above are unchanged and ready to re-run as-is once it is present
  in the harness's environment.

## 2026-08-14: grid trimmed to 6x2 by visible exclusion (mock only)

### Applied
- `tasks.py`: tasks 1 and 6 keep their definitions and their checks byte-for-byte
  and gain an `excluded` string plus a comment giving the reason. Added `GRID`
  (tasks 2, 3, 4, 5, 7, 8) and `EXCLUDED` (tasks 1, 6) derived from that flag,
  so the grid membership is computed from the stated reason rather than from a
  hand-maintained second list. No renumbering; task 3 is still the hero task.
- `harness.py`: `--all` iterates `GRID`; `--task N` still accepts all 8 ids, and
  running an excluded one prints `[note] task N is excluded from the --all grid:
  <reason>`. The summary block now opens with the grid membership and one line
  per excluded task including its reason, so the exclusions travel with the
  table when it is pasted.
- `harness.py` MockClient: the variant-B script now schedules with Marcus
  instead of Priya, who is unschedulable under the 9-17 band. The smoke test
  covers the success path again — variant B on task 2 reports SUCCESS in mock
  where it previously hit `no_slot`. The variant-A script was left on Priya:
  its two calls are reads that already succeed.

### Verified
- Perfect-play direct-dispatch simulation re-run. All six grid tasks still pass
  for BOTH surfaces, with call counts unchanged from the previous block
  (A: 6/13/5/14/11/4 for tasks 2/3/4/5/7/8; B: 1/1/1/1/2/2). Nothing regressed.
- Excluded tasks behave as ruled: task 1 still passes both surfaces (vacuously),
  task 6 still fails both. Neither appears in `--all`.
- `--all --mock` runs 12 combinations (6x2) and prints both exclusion lines.
  `--variant b --task 1 --mock` still runs on demand and shows the note.
- Transcripts redirected to a scratch dir for all verification; the empty
  `weekend2-demo/transcripts/` from the failed live run is untouched and still
  empty. Scratch deleted. No live API calls, so **no measurement numbers exist
  from this block**; the mock token figures are MockClient constants.
- Files modified vs `e4c2579`: `tasks.py`, `harness.py`, `BUILDLOG.md` only.
  `surface_a.py`, `surface_b.py`, `calendar_world.py` untouched.

### Open
- `find_meeting_time` is still exercised by no task, for the reason recorded in
  the previous entry: it mutates nothing, so an outcome check cannot see it.
- Priya and Elena remain absent from every scheduling task. Restoring them needs
  the 9-17 band widening, which has not been approved.
- The live 6x2 measurement is still outstanding.

## 2026-08-14: tokenizer-true cover charge for both demo surfaces

### Method and code path
- `tiktoken 0.13.0` installed `--user` (satisfies `requirements.txt: tiktoken>=0.7`);
  `o200k_base` vocabulary downloaded and loaded successfully.
- The recipe was **imported, not reimplemented**, so it cannot drift from the
  corpus: `02_count_tokens.py` was loaded via `importlib` and its own
  `compact()` and `build_counter()` were used. `build_counter()` returned
  `tiktoken:o200k_base`, so every figure below is quotable under the
  data-handling rule. Reproduce with:

```python
import importlib.util, sys
spec = importlib.util.spec_from_file_location("count_tokens", "02_count_tokens.py")
ct = importlib.util.module_from_spec(spec); spec.loader.exec_module(ct)
count, method = ct.build_counter()          # -> tiktoken:o200k_base
sys.path.insert(0, "weekend2-demo")
import surface_a, surface_b
count(ct.compact(surface_a.TOOLS))          # -> 1703
count(ct.compact(surface_b.TOOLS))          # -> 719
```

### Numbers (tiktoken:o200k_base, compact/sorted/unicode-kept)
| | tools | cover charge | median tokens/tool | harness `est_tokens()` | est error |
|---|---|---|---|---|---|
| Surface A | 28 | **1,703** | 43 | 2,051 | +20.4% |
| Surface B | 6 | **719** | 106 | 903 | +25.6% |

- Ratio A/B, tokenizer-true: **2.37x** (the estimate put it at 2.27x).
- The README's "~2,050 tokens" is the character heuristic and overstates the
  true count by 348 tokens. Not corrected here — rule 3, human's to write.

### Corpus comparison (data/results.csv, 162 rows, all `tiktoken:o200k_base`)
- Median catalog cost 1,879; 90th percentile 13,488; median tool count 7.0;
  median of per-catalog `median_tool_tokens` 191. (Recomputed from the CSV, and
  they match the figures already in this log.)
- Surface A at 1,703 tokens = **44th percentile, 0.91x the field median**.
- Surface B at 719 tokens = 30th percentile.

### Comparability verdict: NOT strictly apples-to-apples
The corpus rows are real MCP catalogs; `surface_a.TOOLS` is an Anthropic-format
list built by a local `_t()` helper. Measured differences across all 2,401
corpus tools:
- Schema key naming is a non-issue: all 2,401 corpus tools use `inputSchema`,
  Surface A uses `input_schema`, and renaming costs **+0 tokens** under o200k_base.
- Envelope is the real gap. Corpus tools routinely carry keys Surface A has
  none of: `annotations` on 1,324 tools (55%), `title` 1,035 (43%),
  `outputSchema` 973 (41%), `execution` 726 (30%), `_meta` 217 (9%). Inside the
  schema, `$schema` appears on 847 (35%) and `additionalProperties` on 775 (32%);
  Surface A's schemas carry only `type`/`properties`/`required`.
- Adding just the two commonest schema-internal extras to Surface A takes it
  from 1,703 to **2,263 tokens (+33%)**, moving it to the 54th percentile and
  1.20x the median. That is a floor on the correction, not the whole of it —
  it excludes `annotations`, `outputSchema`, `title` and `_meta` entirely.
- So Surface A as authored is **leaner** than a real registry catalog carrying
  the same tools. The direction favours honesty about A (it is not padded to
  win the argument), but it means the median comparison is being made against
  rows that include envelope A does not pay for.

### The composition caveat the "typical public server" claim depends on
Surface A only lands near the median in total because two atypical properties
cancel:
- 28 tools = **86th percentile** by tool count (only 23 of 162 catalogs have >=28).
- 43 tokens/tool = **0th percentile** by per-tool cost, against a field median
  of 191 tokens/tool.
A is therefore a large, unusually terse catalog, not a median-shaped one.
Surface B, at 6 tools, is nearer to typical on tool count (48th percentile) with
per-tool cost at the 16th percentile.

### Not done, deliberately
- `weekend2-demo/README.md`'s cover-charge sentence and
  `methods_note_template.md` were left untouched (AGENTS.md rule 3).
- No permanent script was added for this statistic; the snippet above is the
  reproducible origin. Proposed: promote it to `04_cover_charge.py` so the
  number regenerates like the rest of the derived data.
- Still no live API runs, so there remain no measured token or verdict numbers
  for the A/B comparison itself.

## 2026-08-14: cover charge promoted to a tracked script

### Applied
- Added `04_cover_charge.py` at the repo root, beside `01_`/`02_`/`03_`. (The
  scripts live at the root; `AGENTS.md` still describes a `weekend1-starter/`
  directory that does not exist. Followed the repo, not the doc.)
- It is now the reproducible origin for the cover-charge statistic recorded in
  the previous entry, replacing the inline snippet there.
- The recipe is imported, never reimplemented: `importlib.util.spec_from_file_location`
  loads `02_count_tokens.py` (its leading digit blocks a normal import) and the
  script calls that module's own `compact()` and `build_counter()`. Nothing is
  hardcoded — every figure, including the corpus median, 90th percentile and all
  percentiles, is recomputed from `data/results.csv` and `data/raw/` at run time.
- Output is stdout only. No file is written anywhere, so no new derived data and
  no data-dictionary question.

### Verified
- Reproduces the previous entry's figures exactly: Surface A 1,703 tokens,
  Surface B 719 tokens, ratio 2.37x, under `tiktoken:o200k_base`.
- Deterministic: two consecutive runs are byte-identical.
- The estimate guard works. With the tokenizer forced to fail, the script prints
  a NOT QUOTABLE banner, reports `estimate:chars/3.5`, and exits **1**; with the
  real tokenizer it exits 0. That fallback path also confirms where the README's
  "~2,050" came from — the estimate counter returns exactly 2,051 for Surface A
  and 903 for Surface B.
- `git status` shows only the new untracked script; `data/` is unchanged.

### Not done
- Not committed and not pushed; the human reviews the script first.
- No CSV output. Proposed instead of applied: if this should feed a chart or the
  methods note, a `data/cover_charge.csv` would need new data-dictionary fields,
  which is a methods-note change and therefore human territory.
- `weekend2-demo/README.md`'s "~2,050 tokens" sentence and
  `methods_note_template.md` remain untouched (AGENTS.md rule 3).
