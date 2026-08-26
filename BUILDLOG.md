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

## 2026-08-14: demo plumbing shakedown (mock only, agent block)

### What ran
- Environment: Python 3.9.6. No live API calls, no `ANTHROPIC_API_KEY` used,
  no `--all` grid. Mock only, so there are **no measurement numbers from this
  block** — MockClient emits synthetic token counts and its verdicts are
  meaningless by design.
- All 12 combinations (variants a/b x tasks 1-6) complete the agent loop in
  `--mock` without error. No 3.9 syntax problems in any module.
- Verification ran from a scratch dir with `harness.TRANSCRIPT_DIR` redirected,
  so `demo/transcripts/` was never created. Scratch dir deleted after.

### Changed (in-lane)
- `harness.py`: transcript path was CWD-relative (`Path("transcripts")`), so the
  invocation documented in AGENTS.md (`python demo/harness.py`) would
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

## 2026-08-14: demo task redesign against human rulings (mock only)

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
  dir; `demo/transcripts/` was never created. Scratch deleted.
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

## 2026-08-14: First commit of demo + guardrails (agent block)

### Applied
- Commit `e4c2579` on `main`: 13 files, 1110 insertions. demo
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
`demo/`, Python 3.9.6, `anthropic` 0.122.0:

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
  `demo/transcripts/` from the failed live run is untouched and still
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
sys.path.insert(0, "demo")
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
- `demo/README.md`'s cover-charge sentence and
  `methods_note_template.md` were left untouched (AGENTS.md rule 3).
- No permanent script was added for this statistic; the snippet above is the
  reproducible origin. Proposed: promote it to `04_cover_charge.py` so the
  number regenerates like the rest of the derived data.
- Still no live API runs, so there remain no measured token or verdict numbers
  for the A/B comparison itself.

## 2026-08-14: cover charge promoted to a tracked script

### Applied
- Added `04_cover_charge.py` at the repo root, beside `01_`/`02_`/`03_`. (The
  scripts live at the root; `AGENTS.md` still described a separate starter
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
- `demo/README.md`'s "~2,050 tokens" sentence and
  `methods_note_template.md` remain untouched (AGENTS.md rule 3).

## 2026-08-14: Gemini added as a second provider to the harness (mock only)

### Why
The human has no Anthropic key and does have a free Google AI Studio key. The
Anthropic path is left intact for whenever a key appears; Gemini is an
alternative, not a replacement.

### Verified against the docs and against the installed SDK
- Package: `google-genai`, imported `from google import genai`. The old
  `google-generativeai` is deprecated with support ended **2025-11-30**
  (ai.google.dev/gemini-api/docs/libraries, and the PyPI page for the old
  package). Installed 1.47.0 `--user`.
- Call shape: `client.models.generate_content(model=..., contents=[...],
  config=types.GenerateContentConfig(system_instruction=..., tools=[...]))`.
  The docs banner now pushes a newer **Interactions API**
  (`client.interactions.create`, "only works for SDK newer than 2.0.0");
  `hasattr(genai.Client, "interactions")` is **False** on 1.47.0, so
  `models.generate_content` is the correct call here.
- Token fields, read off `types.GenerateContentResponseUsageMetadata` rather
  than from prose: `prompt_token_count`, `candidates_token_count`,
  `cached_content_token_count`, `thoughts_token_count`,
  `tool_use_prompt_token_count`, `total_token_count`. Semantics confirmed from
  the aiplatform `UsageMetadata` proto and the js-genai type reference:
  `total = prompt + candidates + tool_use_prompt + thoughts`;
  `candidates` **excludes** thinking; `cached_content_token_count` is a
  **subset of** `prompt_token_count`, not an addition to it.
- Free tier, from ai.google.dev/gemini-api/docs/pricing (Standard rows reading
  "Free of charge"): `gemini-3.6-flash`, `gemini-3.5-flash`,
  `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`. Pro models read
  "Not available" on the free tier. `gemini-3.7-flash` is listed as new stable
  on the models page but has **no pricing section**, so its free-tier status is
  unverified and it was not chosen as the default. Per-model RPM/RPD are no
  longer published; the rate-limits page defers to AI Studio.
- `Part.from_function_response` on 1.47.0 has signature
  `(*, name, response, parts=None)` — **no `id` kwarg**, unlike the current docs
  example. So the harness builds
  `types.Part(function_response=types.FunctionResponse(id=..., name=..., response=...))`
  directly, which does carry the id.

### Applied (`harness.py` only)
- `--provider {anthropic,gemini}` and a per-provider `--model` default:
  `MODEL_DEFAULT` stays `claude-sonnet-4-6` (still line-quotable), plus
  `GEMINI_MODEL_DEFAULT = gemini-3.6-flash`. `--model` overrides either.
- `to_gemini_declarations(tools)`: the converter. Two rules, both pure functions
  of the tool list, so A and B run the same code:
  1. `input_schema` passes through **verbatim** as `parameters_json_schema`.
     Gemini's typed `parameters` field is an OpenAPI 3.0 subset whose
     `types.Schema.enum` is `Optional[list[str]]`, which **rejects** Surface B's
     `duration_minutes: {"type":"integer","enum":[15,30,45,60]}` (reproduced: a
     pydantic ValidationError). Taking that path would mean rewriting B's schema
     and not A's — the exact asymmetry the fairness doctrine forbids.
  2. A tool with empty `properties` is declared with **no parameters field at
     all**. Fires on the four Surface A tools (`list_rooms`, `get_current_time`,
     `get_notification_settings`, `get_user_preferences`) and on zero Surface B
     tools, because only A owns no-argument tools. Same rule, different input.
- Loop adapted: function-call parts in, function-response parts back. The
  model's own `Content` object is appended **verbatim** before the results,
  because Gemini 3 requires `thought_signature` parts to return inside the Part
  they arrived in; rebuilding the turn from the normalized dict would strip them.
- `gemini_to_plain()` normalizes into the existing plain shape, so one loop, one
  meter and one summary table serve both providers. `tin` gets
  prompt + tool_use_prompt, `tout` gets candidates + thoughts; those two sums
  reconcile to `total_token_count` exactly, and a per-turn guard prints `[warn]`
  if they ever fail to. Cached tokens are **reported, never added** (they are
  already inside `prompt_token_count`). A second guard warns on any
  `finish_reason` other than `STOP`, so a truncated turn cannot pass silently.
- `MAX_OUTPUT_TOKENS` stays 1024 for Anthropic. `GEMINI_MAX_OUTPUT_TOKENS` is
  4096 because Gemini 3.x Flash bills thinking against that budget and 1024
  would truncate turns before a tool call appeared. Applied identically to both
  surfaces, so B gains no turn-budget advantage. **Flagged for ratification:**
  this is a harness knob, but it is the one number in this block that could be
  argued to touch the comparison.
- `MAX_TURNS` unchanged at 25 for both providers.

### Verified (mock only, no live call, no key present)
- Anthropic path is **byte-identical** to the pre-change harness: stdout diffed
  across all 10 grid runs (variants a/b x tasks 2,3,4,5,7,8 — 10 of the 12
  compared) and the JSONL transcript bodies compared equal.
- All 16 Gemini combinations (variants a/b x tasks 1-8) run through the real
  argparse path with no exception and **no `[warn]` line**, Python 3.9.6.
- The exact request body was captured by intercepting
  `BaseApiClient.request` — after the body is assembled, before anything is
  sent — with a dummy key. Surface A: 28 declarations, 24 carrying
  `parameters_json_schema`, 0 carrying the legacy `parameters`, 4 with no
  parameters key, **0 shipping an empty `properties` object**, and every
  surviving schema byte-identical to the surface source. Surface B: 6/6/0/0/0,
  same identity check, integer enum intact. Bodies 7,543 and 3,598 compact bytes.
- The SDK ships this field as snake_case `parameters_json_schema` on the Gemini
  Developer API path (there is no `_FunctionDeclaration_to_mldev` converter, only
  a Vertex one, so the fields pass through unrenamed). That is valid ProtoJSON —
  protobuf.dev/programming-guides/json/ states parsers must accept both
  lowerCamelCase and the original proto field name — and python-genai issue
  #1147 plus livekit/agents PR #5560 both record `parameters_json_schema`
  working on the regular `generate_content` path. **Caveat: it does NOT work on
  Live API models**, where it silently yields empty arguments.
- Surfaces are not mutated by conversion: `surface_a.TOOLS` and
  `surface_b.TOOLS` serialize identically before and after.
- Tool results go back as parsed objects, not escaped strings. All 28 Surface A
  and 6 Surface B dispatch outputs parse to dicts, so `to_function_response`'s
  string fallback never fires for either surface.
- Transcripts were redirected to a scratch dir for every check;
  `demo/transcripts/` is still present and still **empty**, as the
  aborted live run left it. Scratch artifacts live outside the repo at
  `/tmp/apitalk_scratch/`, `/tmp/apitalk_scratch2/` and `/tmp/verify_*.py`, and
  were left in place rather than deleted.
- Files modified vs `3ad8f9f`: `demo/harness.py` and this log only.
  `surface_a.py`, `surface_b.py`, `calendar_world.py`, `tasks.py` untouched.
  Seed 1776 untouched. Not committed, not pushed.

### Measured: wire-format serialization cost (report-only, not a live number)
Code path — recipe imported, never reimplemented, per the data-handling rule:

```python
import importlib.util, sys
spec = importlib.util.spec_from_file_location("count_tokens", "02_count_tokens.py")
ct = importlib.util.module_from_spec(spec); spec.loader.exec_module(ct)
count, method = ct.build_counter()          # -> tiktoken:o200k_base
sys.path.insert(0, "demo")
import surface_a, surface_b, harness
count(ct.compact(surface_a.TOOLS))                                    # 1703
count(ct.compact(harness.to_gemini_declarations(surface_a.TOOLS)[0]))  # 1667
count(ct.compact(surface_b.TOOLS))                                    # 719
count(ct.compact(harness.to_gemini_declarations(surface_b.TOOLS)[0]))  # 724
```

| surface | anthropic format | gemini format | delta |
|---|---|---|---|
| A | 1,703 | 1,667 | −2.1% |
| B | 719 | 724 | +0.7% |

- A/B ratio moves from **2.37x to 2.30x**. A shrinks because its four
  no-argument tools shed a whole `{"type":"object","properties":{},"required":[]}`
  block that B never had; B grows slightly because `input_schema` is a shorter
  key than `parameters_json_schema` and B pays that rename on every tool.
- **These are o200k_base counts of Gemini-format JSON.** They measure how much
  JSON each format spends, not what Gemini's own tokenizer would charge.

### Failed / open
- **Nothing here is a live measurement.** No key was present, no request was
  sent, and every token figure in this block is either a MockClient constant or
  an o200k_base count of a serialized catalog.
- The cover-charge statistic in `data/results.csv` and `04_cover_charge.py` is
  `tiktoken:o200k_base`; Gemini uses its own tokenizer. A live Gemini
  `prompt_token_count` is therefore **not comparable** to the corpus median of
  1,879 tokens. Reported, not acted on.
- The SDK ships a local tokenizer (`google.genai.local_tokenizer`) but it needs
  the `sentencepiece` extra and `_local_tokenizer_loader` maps only up to
  Gemini 2.5 (gemma3); there is **no Gemini 3.x entry**, so it cannot price
  `gemini-3.6-flash` offline.
- **Implicit caching is a live threat to the A/B comparison.** It is on by
  default for Gemini 2.5 and newer, with a minimum of 4,096 tokens for the
  Gemini 3 family (2,048 for Gemini 2). Surface A's prompt can cross that floor
  while Surface B's may never reach it, so A could quietly collect a 90%
  discount B is ineligible for. The harness therefore prints cache hits as a
  separate figure and never deducts them. No mitigation applied — this is the
  human's call.
- `gemini-3.6-flash` is a thinking model, so a share of `tout` is thinking
  rather than visible output. The meter breaks it out; the summary table folds
  it into the token total, as it must to stay comparable with Anthropic output.
- Free-tier rate limits are unpublished. A full `--all` grid is 12 runs of up to
  25 turns each, which can plausibly hit an RPM cap; a 429 mid-grid would leave
  a partial table.

## 2026-08-15: Run-environment audit + offline plumbing check (no live runs)

Human asked how to run `demo/` and what to expect. Read-only audit plus
mock runs. No live request was sent, no surface touched, no seed touched.

### Verified
- Both surfaces import and all five demo files parse under the interpreter that
  actually holds the SDKs (`/usr/bin/python3`, 3.9.6).
- `--mock` completes the full loop on both providers: `a/1` and `b/3` on the
  Anthropic path, `a/3` on the Gemini path (parses function calls, reads usage
  fields, exercises the cached column). Cover-charge line reads 28 tools /
  ~2,051 est for A and 6 tools / ~903 est for B; Gemini wire format for A reads
  28 declarations / ~2,048 est, with the four no-argument tools named.
- Mock runs were executed in a throwaway copy at `/tmp/apitalk_mockcheck`
  (since deleted), so no constant-valued JSONL landed in `transcripts/`.
  `transcripts/` remains empty — still zero live runs on record.
- Working tree clean against HEAD before this entry.

### Failed / open
- **The documented command `python …` does not work on this machine.** `python`
  resolves to `/opt/anaconda3/bin/python` (3.12.7), which has neither
  `anthropic` nor `google-genai`. `python3` resolves to `/usr/bin/python3`
  (3.9.6), which has both, installed into user site-packages. `AGENTS.md` and
  `demo/README.md` both say `python`. Not corrected — doc wording and
  whether to build a venv are the human's call. `.venv/` and `venv/` exist at
  the repo root but are both empty.
- **`ANTHROPIC_API_KEY` is not set**, so the pinned default measured model
  (`claude-sonnet-4-6`) cannot run. `GEMINI_API_KEY` is set, so
  `--provider gemini` is the only live path currently available.
- 3.9.6 is past end of life; `google-auth` and `urllib3` emit warnings on every
  Gemini run. Cosmetic for correctness, but they land in the recording frame.
- Switching providers to get a live number changes the measured agent. The
  A-vs-B comparison stays internally valid only if both sides run on the same
  provider and model; a Gemini grid is not comparable to an Anthropic grid, and
  its `prompt_token_count` is not comparable to the corpus `o200k_base` median.
  Reported, not acted on.

## 2026-08-15: Gemini live path unblocked; grid attempted, NOT completed

Human authorized a live `--all` grid on Gemini (accepting it as a separate
experiment from the Anthropic numbers) and a docs fix. The grid did not run to
completion. **No summary table exists. No live A/B numbers were produced.**

### Changed (in-lane)
- `harness.py`, `GeminiSession.__init__`: was `self.models = genai.Client().models`,
  which keeps the `models` accessor but drops the last reference to the `Client`
  that owns it. The `Client` is then garbage collected, collection closes the
  shared httpx transport, and the first `generate_content` raises
  `RuntimeError: Cannot send a request, as the client has been closed`. Now the
  `Client` is held on the session. Provider plumbing only — it fires identically
  for Surface A and Surface B, touches no surface, no seed, no scoring.
- `AGENTS.md` and `demo/README.md`: `python`/`pip` -> `python3`/
  `python3 -m pip`, with a note naming `/usr/bin/python3` as the interpreter
  holding the SDKs. Bare `pip` resolves to Anaconda's, same failure mode as
  bare `python`.

### Verified
- Root cause reproduced directly, not inferred: discarding the `Client` and
  keeping only `.models` fails with the closed-transport error; holding the
  `Client` succeeds. Both patterns run back to back in one process.
- A minimal live call to `gemini-3.6-flash` succeeds and returns usage
  (`prompt_token_count=7`, `candidates_token_count=1`, `thoughts_token_count=95`
  for a two-word prompt — thinking dominates at small sizes).
- Gemini `--mock` path still passes after the fix (`b/3`, unchanged constants).
- The first failure was NOT a sandbox artifact; it reproduced with the sandbox
  fully disabled.

### Failed / open
- **The grid never ran.** Two attempts died on the client bug before the fix;
  the post-fix attempt never launched because the agent's shell environment
  stopped returning exit statuses. No transcript from any live grid run exists.
- **A mock transcript is now sitting in `demo/transcripts/`:**
  `a_task1_1786777881.jsonl`, from a human-run `--variant a --task 1 --mock` in
  a separate terminal. Every number in it is a `MockClient` constant, not a
  measurement, and the folder is otherwise the live-evidence store. Left in
  place — deleting from `transcripts/` is not the agent's call. Flagged for the
  human to remove or annotate.
- Live Gemini latency is ~10-25s per call with thinking enabled. A 12-run grid
  of up to 25 turns each is plausibly 30-90 minutes, on top of the unpublished
  free-tier rate limits already noted above.

## 2026-08-15: First live grid attempt — killed by free-tier 429 at run 1

Human ran `--provider gemini --all`. It died inside the first run (variant A,
task 2) on turn 7. **No grid completed. No summary table. Still no live A/B
numbers.** Console captured at `/tmp/gemini_grid.log`.

### Measured: the free-tier limit is now a known quantity, not a guess
The 429 body names it: metric
`generativelanguage.googleapis.com/generate_content_free_tier_requests`, quotaId
`GenerateRequestsPerMinutePerProjectPerModel-FreeTier`, **quotaValue 5** for
`gemini-3.6-flash`, with `retryDelay: 57s`. Five requests per minute per model.
One harness turn is one request. The earlier BUILDLOG note that free-tier limits
were "unpublished" can be retired for this model.

### Observed (partial run, NOT a result)
Variant A / task 2 reached turn 6 and 13 tool calls at 32,244 input / 2,828
output tokens without finishing, on "Schedule 30 minutes with Marcus next week."
Call sequence included `get_working_hours` and `get_contact_timezone` twice
each. Directionally this is the thesis, but the run was killed mid-flight and
scored nothing, so it is an observation about a crashed trace and must not be
quoted as a measurement.

### Changed (in-lane)
- `harness.py`: `GeminiSession` now retries 429s instead of letting one abort
  the grid, waiting the delay the server itself specifies (RetryInfo block, then
  the prose "retry in Ns", then exponential fallback), up to 8 attempts and
  120s per wait. Each wait prints a visible `[rate-limit]` line.
- Fairness: this is transport behaviour, identical for both surfaces, and a
  waited-out 429 spends no tokens — it cannot move `tokens` or `calls`. It does
  inflate the per-run `secs` figure, and it inflates it *more for Surface A*,
  since A needs more turns and therefore trips the limit more often. `secs` is
  not in the summary table; do not start quoting it without accounting for this.

### Failed / open
- **Unverified by execution.** The agent's shell has been unresponsive since
  before this edit, so the retry path has not been run even in `--mock`. Syntax
  and logic reviewed by reading only. Verify before trusting a long run.
- **`--all` still has no resume.** Any abort restarts at task 2 variant A and
  re-spends quota on work that already succeeded. At 5 RPM this is the dominant
  cost of a failed attempt. Not fixed: making the grid skip or resume completed
  runs changes what a published table represents, so it is the human's call.
- A full grid is plausibly 100-150 requests. At 5 RPM that is a floor of roughly
  20-30 minutes of pure waiting, before model latency.
- Free-tier daily request caps (RPD) are a separate quota from this per-minute
  one and have not been hit or characterised yet.

### Added: `--all --resume` (human-requested)
Opt-in. Off by default, so a plain `--all` is still a single clean sitting.

- Completed, scored runs are written to `demo/runs/` as one JSON row
  each. `--resume` reuses them instead of re-spending quota; everything else
  is measured normally.
- **Resume keys on a completed row, not on a transcript.** A transcript cannot
  reconstruct a table row: `ok` comes from running `task["check"](world)`
  against final world state, and world state is not in the transcript. Skipping
  on transcript existence would also have skipped the crashed task-2 run above,
  whose transcript exists but whose run never finished — silently dropping a
  row or reporting an unscored one. A row is saved only after scoring, so
  interrupted runs leave no row and are re-run.
- Each row stores a 12-char SHA-256 of that surface's `TOOLS`. A cached row is
  refused if the fingerprint no longer matches, because a resumed row measured
  against an older catalog would sit in the same table as fresh rows while
  being incomparable to them. Model and provider are in the filename, so they
  cannot cross-contaminate either.
- Mock runs are never cached; caching constants would let a later `--resume`
  seed a real table with fabricated numbers.
- Resumed rows print `*` in the table, plus a footer naming how many rows came
  from earlier sittings and when. A table that mixes sittings says so on its
  face rather than in someone's memory.

### Failed / open (resume)
- **Also unverified by execution** — same dead shell. Neither the retry nor the
  resume path has been run. Syntax and logic reviewed by reading only.
- Resume deliberately does not check whether `harness.py` itself changed between
  sittings, only the surface catalog. A harness edit that altered measurement
  would not invalidate cached rows. Fingerprinting the harness was not done
  unasked; flagged for the human.

## 2026-08-15 (morning): The Gemini free tier cannot run this grid — 20/day

### Measured: there are TWO free-tier quotas, and the binding one is per-day
Last night's 429 named `GenerateRequestsPerMinutePerProjectPerModel-FreeTier`,
quotaValue **5** — a burst limit. This morning's names
`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, quotaValue **20** for
`gemini-3.6-flash`. Twenty requests per day, and one harness turn is one
request.

Surface A alone spent 13 tool calls across 6 turns on task 2 without finishing.
A full 6x2 grid is on the order of 100+ requests. **The grid is roughly five
times the entire daily free-tier allowance, so it cannot complete on this tier
at any pacing.** Even the two hero clips the recording plan needs (task 3 on A and B)
are ~18 requests, i.e. essentially the whole day's budget with nothing left for
a retake.

Today's allowance is spent. Nothing further runs on this key until the daily
boundary.

### Changed (in-lane)
- `harness.py`: added `Pacer`, holding requests to a fixed minimum spacing,
  applied in the shared `run()` loop so it covers both providers. Interval is
  per-provider (`MIN_REQUEST_INTERVAL`: gemini 12.0s = 60/5, anthropic 0.0) and
  overridable with `--min-interval`; `--min-interval 0` disables it, which is
  what recording takes should use so the meter does not sit idle between turns.
  Pacing is skipped entirely for `--mock`. Per-run `paced_secs` is now in the
  result row and printed beside `secs`, so wall-clock stays interpretable.
- `harness.py`: fixed a retry bug this run exposed. A per-day 429 carries
  `retryDelay: 0s`, so the loop spun attempts 2-5 in about a second and
  reported exhaustion rather than the real cause. Retries now floor at
  `RATE_LIMIT_MIN_WAIT` (5s), and `is_daily_quota()` refuses to retry a per-day
  cap at all, printing that pacing and retrying are both powerless against it.

### Verified
- `Pacer(1.0)` over four calls waits `[0, 1, 1, 1]`, elapsed 3.01s, no drift;
  `Pacer(0)` is a no-op.
- Pacing engaged live: `[pace] holding requests 12s apart (5/min)`.
- The retry safety net works live — it absorbed two per-minute 429s and the run
  proceeded to turn 1 and three tool calls.
- `is_daily_quota` returns True for the per-day violation and the string
  fallback, False for the per-minute one and for unrelated errors. The 0.539s
  server delay now floors to 5.0s.

### Failed / open
- **Still zero completed live runs.** `demo/runs/` is empty, no summary
  table has ever been produced, and there are still no live A/B numbers of any
  kind. Every token figure quoted anywhere so far is either a mock constant, an
  offline tokenizer count, or a partial from a killed run.
- Pacing addressed the per-minute limit, which turned out not to be the binding
  constraint. It is correct and worth keeping, but it did not and cannot solve
  this. Recorded plainly so the next session does not re-derive it.
- The per-day reset boundary was not confirmed from the API (commonly midnight
  Pacific, unverified here). Do not plan around an assumed reset time.
- Decision now belongs to the human: paid tier on Google, an Anthropic key for
  the pinned `claude-sonnet-4-6`, a different free model with a larger daily
  cap (changes the measured agent), or scoping the run down to what 20
  requests/day can actually buy.

## 2026-08-15 (midday): Spike — can the Cursor SDK drive the frozen surfaces?

Human has LLM access through a Cursor enterprise plan and asked whether it can
be used from code. Built a standalone spike, **not** wired into `harness.py`.
`spike_cursor_sdk.py` imports the surfaces read-only, writes no transcript, and
touches neither `transcripts/` nor `runs/`.

### Environment: consolidation ATTEMPTED AND FAILED — correcting this entry
`cursor-sdk` requires Python >=3.10, so `/usr/bin/python3` (3.9.6) cannot host
it — `pip index` reports no matching distribution there. Installed
`cursor-sdk`, `anthropic` (0.122.0) and `google-genai` (2.18.1) into
`/opt/anaconda3/bin/python` (3.12.7).

**This entry originally claimed all three SDKs now share one interpreter. That
is false and is corrected here rather than rewritten away.** Under Anaconda,
`from google.genai import types` **segfaults on import** (exit 139), before any
harness code runs. Anaconda ships `libprotobuf.25.3.0.dylib` with pip
`protobuf` 4.25.3, and google-genai 2.18.1 crashes against that pairing.
Forcing `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` does not help — still
139. Not pursued further: base-env protobuf surgery risks other conda packages,
and the Gemini free tier is a dead end regardless.

**Standing rule until someone fixes it:**

| provider | interpreter |
|---|---|
| cursor, anthropic | `/opt/anaconda3/bin/python` (3.12.7) |
| gemini | `/usr/bin/python3` (3.9.6) |

No single interpreter runs all three. The `python3` guidance added to AGENTS.md
and the demo README this morning points at the 3.9 one, which has no
`cursor-sdk`. Docs not re-edited — which interpreter is canonical is the
human's call.

### Verified by introspection, not from docs
- `AgentOptions` carries `tools` / `disallowed_tools`; `LocalAgentOptions`
  carries `custom_tools`. `CustomTool(execute, description, input_schema)`.
- `TokenUsage(input_tokens, output_tokens, cache_read_tokens,
  cache_write_tokens, total_tokens, reasoning_tokens)` — the fields the meter
  needs exist.

### Q1 ANSWERED (offline, no key): the surfaces transfer verbatim
Surface A 28 tools -> 28 `CustomTool`; Surface B 6 -> 6; every tool converted;
`input_schema` passes through **by identity**, not copied or reshaped, so no
asymmetric rewrite can creep in the way it did for the Gemini wire format; and
`execute()` reaches `surface.dispatch` and returns real payloads
(`list_contacts` 459 chars, `get_schedule_summary` 107 chars).

### Open — blocked on `CURSOR_API_KEY`, which is not set
- **Q2** does the agent actually call the surface tools and mutate the world?
- **Q3** do per-turn `usage` stream events fire, so the meter survives?
- **Q4** does `tools=["mcp"]` genuinely exclude Cursor's built-ins? The docs say
  an empty allowlist offers no built-ins and that disallowing `"mcp"` also drops
  custom tools, which is why the spike allowlists `["mcp"]` rather than passing
  `[]`. **Unverified.** If built-ins leak in, the cover charge measures Cursor's
  toolset plus the surface and no token number from this path means anything.

### Risks to record regardless of how the spike lands
- The system prompt is not ours. Cursor's own prompt and scaffolding land inside
  `input_tokens`. Constant across A and B, so the *gap* survives, but absolute
  numbers stop being comparable to the corpus median of 1,879 or to any
  Anthropic-direct run — and the cover-charge claim leans on that comparability.
- The agent loop is not ours either: `MAX_TURNS`, context handling and any
  compaction belong to Cursor. Compaction would directly bend the token growth
  curve the demo exists to show.
- `README.md` opens by warning against conflating the editor's agent with the
  measured agent. This path merges them. Defensible if said out loud on stage;
  it is a choice, not a detail, and it is the human's to make.

### Merged into the harness (human-requested): `--provider cursor`
The standalone `spike_cursor_sdk.py` is gone; its behaviour now lives in
`harness.py` and its `--list-models` diagnostic is a harness flag.

- `CursorSession` does **not** implement `send()`/`record()`, because it cannot
  do so honestly. The other two sessions return one model turn and let `run()`
  dispatch the tools and decide whether to continue; the Cursor SDK runs the
  whole conversation inside `agent.send()` and invokes tools through the
  `execute` callbacks. So it sets `owns_loop = True` and exposes `turns()`, and
  `run()` takes a separate branch that accounts for what the SDK reports rather
  than pretending to drive the loop.
- Per-turn rows come from the SDK's `usage` stream events. Tool calls are
  attributed to a turn by the growth of the `calls` list between those events,
  which is exact — the callbacks fire on real invocations — rather than parsed
  out of a model reply.
- `tools=["mcp"]` allowlists only the group carrying custom tools, so Cursor's
  built-in read/edit/shell are not offered. **Still unverified live.** If they
  leak in, the cover charge is Cursor's toolset plus the surface and no token
  figure from this provider means anything.
- `MAX_TURNS` does not bind on this path and `secs` excludes pacing
  (`paced_secs` is 0; `MIN_REQUEST_INTERVAL["cursor"]` is 0.0, no known cap).

### Verified
- Providers register as `['anthropic', 'cursor', 'gemini']` with per-provider
  model defaults and intervals.
- `--provider cursor --mock` completes the loop for surface A and B, driving the
  real `CustomTool.execute` callbacks into `surface.dispatch`, with constant
  token figures as the other mocks do.
- Anthropic and Cursor mock rows are identical (4,960 tokens, 2 calls) under
  Anaconda; the Gemini mock cannot run there at all (segfault above).
- Regression runs used a redirected `harness.TRANSCRIPT_DIR`, per the pattern
  from 2026-08-14, so `transcripts/` was not written to. One mock transcript
  *was* created before that (`a_task2_1786815481.jsonl`) and was deleted —
  it was an agent-made artefact from this session, not testimony.

## 2026-08-15 (late morning): `--provider cursor` runs live. First live runs.

Human supplied `CURSOR_API_KEY`. Three live runs of variant A / task 2, ~50s
each. **These are verification runs, not measurements** — see the token finding
below for why nothing here is quotable as a result.

### The pinned model is available on this plan
`--list-models` returns 36 ids including **`claude-sonnet-4-6`**, which is
exactly `MODEL_DEFAULT`. `CURSOR_MODEL_DEFAULT` was changed from a guessed id
(`claude-4.6-sonnet-medium-thinking`, not offered to this account) to
`MODEL_DEFAULT`, so both paths name the same model. That makes
cursor-vs-anthropic a comparison of the surrounding agent loop rather than of
two different models. `gemini-3.6-flash` is also on the list.

### Built-in tools: NOT used; whether they were OFFERED is still unknown
All 9 tool calls were surface tools (`get_current_time`, `search_contacts`,
`get_free_busy`, `get_user_preferences`, `get_working_hours`, `create_event`,
`send_invite`, ...). The SDK reports every custom tool under an envelope named
`mcp`, carrying the real name inside `args` — the first detector flagged `mcp`
itself as foreign, a false positive now fixed by unwrapping `args.toolName`.
No `read`/`edit`/`shell` appeared. **But the SDK emitted no `system` message on
any of the three runs, and `system.tools` is the only field that reports the
offered catalog, so `tools=["mcp"]` remains unconfirmed.** Not-used is weaker
evidence than not-offered, and cover charge depends on what is offered.

### DECISIVE: the token numbers are not comparable, catalog question or not
53,053 input tokens for a surface whose own cover charge is ~2,051. Roughly 50k
of that is Cursor's system prompt, scaffolding and context. For scale, the same
task on Gemini reached 32,244 input across six turns *cumulatively*. Whatever
the catalog turns out to be, this provider cannot be compared against
anthropic or gemini rows, nor against the corpus median.

### The per-turn meter does not survive this path
Exactly **one** `usage` event fired per run, covering the whole conversation, so
the meter collapses to a single row. The turn-by-turn climb — "the meter is the
show" — does not exist here. Recorded as a property of the path, not a bug to
paper over.

### Observed: Surface A failed the task while reporting success
Scored FAIL on all three runs while the agent's final message claimed the
meeting was booked and the invite sent. The transcript (now carrying real tool
arguments) shows why:

```
create_event -> {"calendar_id":"cal_you","summary":"Q3 Roadmap Discussion",
                 "start":"2026-08-17T13:00:00-04:00","end":"...13:30:00-04:00"}
send_invite  -> {"event_id":"evt_207","contact_id":"marcus"}
```

`create_event` accepts an optional `attendee_ids`; it was not passed, so the
surface defaulted the event to `["you"]`. `add_event_attendee` exists and was
never called. The model created a meeting with only itself on it, sent Marcus an
invite, and reported success. The task check requires
`set(attendees) == {"you","marcus"}`, so it correctly scored FAIL.

**This is a genuine Surface A outcome, not a harness or scoring bug**, and it is
the thesis in a live trace: a 1:1 endpoint wrapper lets a competent model skip a
step in a three-call choreography and be unable to tell. Caveats that must
travel with it: one task, three runs, on the non-comparable provider, from
verification runs rather than a scored grid.

### Failed / open
- `tools=["mcp"]` still unconfirmed; needs a run where the SDK emits `system`,
  or another way to read the offered catalog.
- Transcript `input` stores the whole SDK envelope
  (`providerIdentifier`/`toolName`/`args`) rather than the inner args. Readable,
  but not the same shape the other two providers write.
- Three live runs wrote three transcripts to `transcripts/`. Real runs, so they
  were left in place.

## 2026-08-15 (midday): FIRST COMPLETE GRID. Provider: cursor. Tokens NOT quotable.

`--provider cursor --all --resume`, 12 runs, ~8.5 minutes, no quota trouble.
Twelve rows cached in `demo/runs/`. **Read the caveats before using
any number here.**

```
provider: cursor | model: claude-sonnet-4-6
grid: tasks 2, 3, 4, 5, 7, 8 (6 of 8 defined tasks)
  excluded task 1: always-true check; the row reports SUCCESS regardless of behaviour
  excluded task 6: unpassable by both surfaces: 'you' has no Friday meetings ...
task |   A ok  A tokens A calls |   B ok  B tokens B calls
   2 |  False    61,609      10 |   True    17,245       1
   3 |   True    95,607      20 |   True    19,107       1
   4 |   True    65,107      10 |   True    53,689       8
   5 |   True   103,544      19 |   True    17,359       1
   7 |   True    70,740      16 |   True    35,279       3
   8 |   True    55,607       8 |   True    54,160       9
```

### Divergent row (the grid prompt asks for these to be flagged)
**Task 2: A FAIL, B SUCCESS.** Cause established from the transcript earlier
today: `create_event` was called without its optional `attendee_ids`, so the
surface defaulted the event to `["you"]`; `add_event_attendee` was never called;
`send_invite` fired anyway and the agent reported success. A meeting was created
that Marcus is not on. Genuine Surface A behaviour, correctly scored.

### The call-count column is the cleanest result here
It is the one column Cursor's scaffolding does not distort. A needed 10-20 calls
where B needed 1 on the same task (2, 3, 5), and A's hero-task run took 20 calls
against B's 1.

Two rows are narrow, and both were **predicted in `tasks.py` before any run**:
task 8 says "Suits Surface A ... B must first locate the day before it can
cancel, so the gap here should be narrow" — measured A 8, B 9, i.e. B spent
*more*. Task 4 came out A 10, B 8. The task design anticipated its own
counterexamples, which is worth saying on stage.

### Caveats — why the token columns are not quotable
- Cursor's own scaffolding sets a floor: B's single-call runs cost 17,245 and
  17,359 tokens for one tool call. That floor is not present on a raw-API run,
  so these totals cannot be compared with anthropic/gemini rows or with the
  corpus median. The A/B *ordering* survives; the *ratio* does not.
- One `usage` event per run, so `secs` and the token total are whole-run figures
  and there is no per-turn curve behind them.
- One run per cell. No repeats, so no variance estimate and no claim about
  stability.
- Task 5 injects a transient 503 on room booking. Both surfaces still succeeded;
  A spent 19 calls / 103s. The error-tax beat did not produce a failure here.
- Whether Cursor's built-in tools were *offered* remains unverified (no `system`
  message on any run); none were *used* in any of the 12 runs.

### Docs updated (human-requested)
`AGENTS.md` and `demo/README.md` now carry the per-provider interpreter
table instead of the stale "use python3" line.

## 2026-08-15: Tasks 9 and 10 added — PREDICTIONS REGISTERED BEFORE ANY RUN

Human asked whether the tasks could be restructured to show a starker A/B gap,
then chose to **add** tasks rather than change existing ones, and to **keep
tasks 4 and 8** (the narrow rows) in the grid. This entry is written before
either new task has been run even once; the results go in a separate entry
below it so the order is auditable.

Note first that the tasks were probably never the problem: the call column
already reads 20-vs-1 on task 3. What flattened the token column was Cursor's
~17k floor, not task design.

### Why these two, on principled grounds
The grid tested three shapes — two-person, three-person-plus-room, and
find-then-modify — but never **repetition** (the same choreography twice in one
request) and never **additivity** (two independent sub-goals in one request,
beyond task 7's small case). Both are ordinary calendar requests, not shapes
reverse-engineered from Surface A's weaknesses.

- **Task 9, repetition.** Two 30-minute 1:1s, one with Marcus, one with Sam,
  both invited. No room, no notification.
- **Task 10, additivity.** Three-person 60-minute session in Room **Basalt**
  (not Aurora, so it shares no state with task 3), invites, plus a separate
  two-hour focus block.

### Registered predictions (copied from `tasks.py`, written before running)
| task | A predicted | B predicted |
|---|---|---|
| 9 | 16-22 calls (≈2x task 2's 10) | 2 calls |
| 10 | 18-24 calls (task 3's sequence + a focus create) | 2 calls |

Falsifiers, also registered in `tasks.py`:
- Task 9 is falsified if A finishes in ~10 calls by reusing one free/busy sweep
  across both meetings — that would mean the cost amortises and the task adds
  nothing over task 2.
- Task 10 is falsified if B needs more than 2 calls, or if A comes in at or
  below its task 3 count of 20, which would mean the second sub-goal was free.

### Verified passable by BOTH surfaces before running (no repeat of task 6)
Scripted directly against the dispatchers, no model involved:
- Surface B: task 9 True in 2 calls; task 10 True in 2 calls.
- Surface A: task 9 True, task 10 True.

Surface A's *theoretical minimum* is 4 and 5 write calls respectively, excluding
slot search. That matters for fairness: neither task is rigged against A on the
write path. Any gap that shows up is discovery cost — the free/busy sweeps,
contact lookups and timezone checks A has to perform itself — which is precisely
the claim under test rather than an artefact of the task.

### Consequences to note
- `GRID` is now `[2, 3, 4, 5, 7, 8, 9, 10]`, so the published table becomes 8
  rows. Tasks 1 and 6 remain excluded for their existing reasons.
- Surfaces, seeds, scoring of existing tasks, and tasks 4 and 8 are untouched.
  The surface fingerprints are unchanged, so `--all --resume` correctly reuses
  the six cached rows and runs only the four new ones.

## 2026-08-15: Tasks 9 and 10 results — PREDICTIONS FALSIFIED. Task 10 unsafe.

Ran `--provider cursor --all --resume`; the twelve existing rows were reused
(marked `*`) and only the four new runs were measured.

```
task |   A ok  A tokens A calls |   B ok  B tokens B calls
   9 |  False    64,714      13 |   True    28,748       4
  10 |  False    39,972       7 |  False    37,258       6
```

### Predictions vs. outcome — both wrong
| task | A predicted | A actual | B predicted | B actual |
|---|---|---|---|---|
| 9 | 16-22 | **13** | 2 | **4** |
| 10 | 18-24 | **7** | 2 | **6** |

Task 10 hit both of its registered falsifiers: B needed more than 2 calls, and A
came in far below its task 3 count of 20. Task 9 missed on both sides too.

**Why A's counts came in low is the important part, and it is not efficiency.**
A failed both tasks, and a failed run ends early, so its call count is truncated.
This generalises: **call counts are only comparable between two runs that both
succeeded.** Task 3 (20 vs 1, both SUCCESS) is a clean comparison; task 2 (10 vs
1, A FAIL) is not, and neither is task 9. That applies retroactively to the grid
already recorded above and should be stated wherever the call column is quoted.

### Task 10: both surfaces failed, for the same non-diagnostic reason
Neither surface created anything. Both explored and stopped:
- Surface B spent all 6 calls on `get_schedule_summary`, starting with
  `day="next week"` — a token `_day()` cannot parse (it raises ValueError, which
  `dispatch` does not catch, since it only catches KeyError). It never called
  `schedule_meeting` or `block_focus_time`.
- Surface A spent all 7 calls on reads (`get_current_time`, `list_contacts`,
  `list_rooms`, `list_calendars`, `get_working_hours`, `list_events`) and never
  wrote. Its `list_events` window was 2026-08-10 to 08-17 — the week *before*
  the world's `t0` of Monday 2026-08-17.

This is a task defect, not a surface finding: three sub-goals plus an ambiguous
"next week" against a world anchored on next Monday. It was verified passable by
scripting both dispatchers, which proves the *mechanism* exists but says nothing
about whether a model can find it. **Task 10 should not appear in a published
grid in this state.** Left in place, unmodified, pending the human's call —
tuning a task until it passes is the exact move the fairness doctrine forbids,
and the precedent (task 6) is to exclude with the reason stated, not to fix.

### Task 9: a legitimate row, and it reproduces the task 2 failure independently
B succeeded in 4 calls. A failed at 13, and the transcript shows the same defect
found on task 2 this morning, now seen twice on different tasks:

```
create_event -> {"calendar_id":"cal_you","summary":"1:1 You / Marcus",
                 "start":"2026-08-17T16:00:00Z","end":"2026-08-17T16:30:00Z"}
send_invite  -> {"event_id":"evt_207","contact_id":"marcus"}
send_invite  -> {"event_id":"evt_206","contact_id":"sam"}
```

`attendee_ids` omitted again, so the event defaulted to `["you"]`. Only **one**
event was created, for Marcus; Sam never got a meeting. The second `send_invite`
went to `evt_206`, an id the run never created — a seeded event. So Surface A
invited Sam to somebody else's meeting and reported success.

That is a stronger version of the task 2 result: not merely a missing attendee
but a fabricated target. Two independent tasks, same root cause — Surface A
lets a model believe a multi-call choreography completed when it did not.

### Human rulings 2026-08-15, applied
1. **Task 10 excluded**, not revised, with the reason stated in `tasks.py` the
   way task 6's is. It stays runnable via `--task 10`, and its registered
   prediction is preserved verbatim with an `OUTCOME` line appended, so the miss
   remains auditable rather than edited away.
2. **Failed runs are now marked in the summary table.** A `†` follows the call
   count of any FAIL row, with a footer stating that a failed run ends early so
   its totals are truncated rather than small, and that the token and call
   columns are only comparable between runs that both succeeded.

Current published grid — 7 rows, tasks 1, 6 and 10 excluded with reasons:

```
task |   A ok  A tokens A calls |   B ok  B tokens B calls
   2 | False     61,609     10† |  True     17,245       1
   3 |  True     95,607      20 |  True     19,107       1
   4 |  True     65,107      10 |  True     53,689       8
   5 |  True    103,544      19 |  True     17,359       1
   7 |  True     70,740      16 |  True     35,279       3
   8 |  True     55,607       8 |  True     54,160       9
   9 | False     64,714     13† |  True     28,748       4
```

The only fully clean call comparisons (both surfaces succeeded, so neither count
is censored) are tasks 3, 4, 5, 7 and 8 — which read 20-vs-1, 10-vs-8, 19-vs-1,
16-vs-3 and 8-vs-9. Tasks 2 and 9 show Surface A failing outright. Token columns
remain non-quotable on this provider for the reasons recorded above.

## 2026-08-15: Transcripts now record tool OUTPUTS. The 503 is finally on record.

Human asked for the per-run transcripts behind tasks 3, 5, 8 and 9 to write
narration from, specifically the bare "503 Service Unavailable".

### Found: no transcript in this repo had ever recorded a tool result
`run()` wrote the model's response — the `tool_use` blocks — and never the
value `surface.dispatch()` returned. True for every provider since the harness
was written. A grep for "503" across all task-5 transcripts returned one hit,
which was the digits inside `"cache_write_tokens": 29503`. So the error string
Surface A is built to relay had **never been captured by any run that provoked
it**, despite task 5 existing to provoke exactly that.

### Fixed
- `run()`: transcript write moved after dispatch, into `write_turn(resp,
  results)`, so each turn's line now carries a `tool_results` array of
  `{id, name, output}`. Lines written before this change simply lack the field.
- `CursorSession.turns()`: tool_call events are now keyed by `call_id` and
  updated in place when the SDK's `result` field arrives, since the event fires
  repeatedly as status advances. Yields `tool_results` alongside `content`.
- Mock path records outputs too, so `--mock` exercises the same shape.

### Verified live — task 5 re-run on both surfaces
```
A  book_room        -> {"error": "503 Service Unavailable"}
B  schedule_meeting -> {"scheduled": ..., "invites_sent": 2,
                        "note": "Room Aurora booked."}
```
`a_task5_1786826112.jsonl` and `b_task5_1786826189.jsonl`. Both runs SUCCESS;
A took 20 calls / 85,729 tokens, B took 1 call / 20,152.

**Observation, not a change:** Surface B's retry loop sets a note reading
"booked after one automatic retry (transient 503)" and then overwrites it with
"booked." when the second attempt succeeds. So B's transcript carries no trace
of the retry, and the model is never told the infrastructure failed. That is
existing frozen-surface behaviour; left alone. It arguably strengthens the beat
rather than weakening it.

### Also delivered
`MANIFEST.md` at the repo root: every deck artifact with path, row count and
commit SHA, plus an explicit NOT AVAILABLE section covering `data/labels.csv`
(never produced, no seed chosen), the methods note (still an unfilled
template), the absent PDF, and the absence of any Anthropic-provider numbers.
It also records that no "freeze" event exists anywhere in this repo —
`results.csv` and `collect_log.csv` have simply been untouched since `8312ed0`.

## 2026-08-15: THIRD SAMPLE. Reliability is the finding; token totals are not.

`runs/` now appends one JSONL line per sample instead of overwriting, so repeats
accumulate. Samples 1 and 2 were migrated in (sample 1 recovered from git
`c9a3032`, sample 2 from the working tree) before sample 3 was run. The summary
table now reports **medians across samples**, plus a spread column, a `!` on any
cell whose verdict disagreed between samples, and a caution when the thinnest
cell has fewer than 3.

```
task |   A ok  A med tok A cal  A spr |   B ok  B med tok B cal  B spr
   2 |   1/3!     61,609   10†    43% |    3/3     17,297     1    16%
   3 |   2/3!     81,568   17†    34% |    3/3     19,107     1    15%
   4 |    3/3     90,552    10    48% |    3/3     53,689     7    60%
   5 |    3/3    103,544    20    23% |    3/3     19,652     1    16%
   7 |    3/3     82,908    16    30% |    3/3     35,279     3    15%
   8 |    3/3     55,607     7    11% |    3/3     62,255     8    43%
   9 |    0/3     64,714   13†    62% |    3/3     29,991     4    13%
```

### THE RESULT, and it is not a token count
**Surface B completed 21 of 21 runs. Surface A completed 15 of 21 (71%).**
Same model, same world, same seed, same prompts, three samples of seven tasks.
This is reproducible, needs no tokenizer caveat, and survives everything that
makes the token columns unusable.

Per-sample verdicts for the cells that moved:
```
 a_task2: FAIL | OK   | FAIL     1/3
 a_task3: OK   | OK   | FAIL     2/3   <- the hero task
 a_task9: FAIL | FAIL | FAIL     0/3
 b_task3: OK   | OK   | OK       3/3
```

### The hero task is not reliable, which matters for the clips
**Task 3 — the cold open — failed on its third run.** Surface A succeeded twice
and then did not. Any recording plan that assumes one take of `--variant a
--task 3` will behave is wrong; budget for the run failing on camera, or pick
the beat knowing it is 2-in-3.

### Calls are stable; tokens are not
Spread across samples, per cell:
- **tokens: median 27%, max 62%**
- **calls: median 3%, max 60%**

Call counts barely move (a/2 was 10,10,10; a/9 13,13,12; b/3 1,1,1) while token
totals swing by a quarter to two thirds. The call column is the robust
measurement on this provider; the token column is not, independently of the
scaffolding-floor problem already recorded.

### Floor across three samples
A: 5,473 -> 5,712 -> 6,286. B: 5,125 -> 5,364 -> 5,912. Difference: **348, 348,
374**. The absolute floor drifted up ~15% across the day — Cursor's own prompt
is not constant — while the A-minus-B catalog difference stayed within 7%. The
difference is the reproducible part; the absolute floor is not.

### Open
- Floor records still overwrite rather than append; the three values above are
  only recoverable from this log and git history.
- Three samples is enough to show the numbers move, not enough to publish an
  interval. The reliability figure (15/21 vs 21/21) is the claim that currently
  has support.

## 2026-08-15: SECOND SAMPLE. Single-run cells are not stable; one verdict flipped.

Re-ran the whole grid fresh (`--all`, no `--resume`, so nothing was replayed)
plus the floor. Sample 1 is preserved in git at `c9a3032`; `runs/` now holds
sample 2, since the cache stores only the latest run per cell.

```
   cell   ok 1   ok 2 | calls1 calls2 |     tok1     tok2    delta
    a/2  False   True |     10     10 |   61,609   51,462     -16%  <-- FLIPPED
    a/3   True   True |     20     17 |   95,607   81,568     -15%
    a/4   True   True |     10     10 |   65,107   90,552      39%
    a/5   True   True |     19     20 |  103,544  107,145       3%
    a/7   True   True |     16     16 |   70,740   91,989      30%
    a/8   True   True |      8      7 |   55,607   55,022      -1%
    a/9  False  False |     13     13 |   64,714   45,382     -30%
    b/2   True   True |      1      1 |   17,245   17,297       0%
    b/3   True   True |      1      1 |   19,107   17,528      -8%
    b/4   True   True |      8      5 |   53,689   36,134     -33%
    b/5   True   True |      1      1 |   17,359   19,652      13%
    b/7   True   True |      3      3 |   35,279   36,031       2%
    b/8   True   True |      9      7 |   54,160   62,255      15%
    b/9   True   True |      4      4 |   28,748   29,991       4%
```
(`a/10`, `b/10` show 0% because task 10 is excluded from the grid and was not
re-run; those cached rows are stale sample-1 values.)

### What did not reproduce — this is the important one
**Task 2, Surface A flipped from FAIL to SUCCESS.** The finding reported this
morning — Surface A creating a meeting without its attendee and declaring
success — happened in sample 1 and did **not** happen in sample 2. On the
evidence available it is a behaviour Surface A *can* produce, observed once in
two attempts. It must not be stated as what Surface A does.

### What did reproduce
- **Task 9, Surface A failed both times** (13 calls both times). The stronger of
  the two failure findings; sample 1's transcript showed the invented `evt_206`.
- **Task 8 does not favour B**: calls were 8-vs-9 then 7-vs-7. The registered
  counterexample holds.
- **The floor difference is exactly 348 tokens in both samples.** The absolute
  floor moved uniformly (+239 on both surfaces: A 5,473->5,712, B
  5,125->5,364), so the base shifted while the catalog delta stayed identical.
  The catalog cost is the reproducible part of that measurement.

### Magnitude of the noise
Token totals moved by a **median of 13% and up to 39%** per cell between two
runs of an identical configuration — same model, same seed, same surfaces, same
prompts. Call counts moved too (a/3 20->17, b/4 8->5, b/8 9->7).

**Consequence: no single-cell number in this grid should be quoted as a point
estimate, and no per-row claim should rest on one run.** The large ordering
results survive — A takes many more calls than B on tasks 2, 3, 5 in both
samples — but the specific figures do not.

### Open
- `runs/` stores one row per cell, so re-running overwrites the previous sample.
  Keeping N>1 needs a different storage scheme (e.g. append-per-sample plus a
  median across samples). Not built; flagged for the human.
- Two samples cannot give a variance estimate worth publishing. Three or more
  would be the minimum for any per-row claim.

## 2026-08-15: Ruling REVERSED — state the floor, do not subtract it. Floor measured.

Human reversed the subtraction decision recorded below: "state the floor rather
than remove it." The `DERIVED` table and its `--baseline-tokens` /
`--no-derived` flags are removed. `--measure-floor` replaces them.

### Method
A control request that needs no tool — `"Reply with exactly the word OK. Do not
call any tool."` — sent through the identical path, once per surface, with the
surface loaded but unused. Cached in `runs/` as `floor_*.json` against the
surface fingerprint, and printed under every grid table. Never subtracted.

### Measured: provider cursor, model claude-sonnet-4-6
| surface | tools | floor tokens |
|---|---|---|
| A | 28 | **5,473** (5,469 in / 4 out) |
| B | 6 | **5,125** (5,121 in / 4 out) |
| difference | | **348** |

### This number changes the reading of the grid, and not in the talk's favour
**A's catalog costs only 348 more tokens per turn than B's, through this path.**
The offline `o200k_base` counts recorded earlier put the two catalogs at 1,703
and 719 — a 984-token gap and a 2.37x ratio. Through Cursor the observed gap is
about a third of that.

So on this provider the *cover charge* is not what separates the surfaces. A
ran 55k-103k against B's 17k-54k while the catalog difference is 348 tokens a
turn. The gap therefore comes from **turn count and payload volume** — A's
verbose responses accumulating across many more turns — not from the size of
the tool list at the top of the context.

That is a real distinction and it cuts against the simplest version of the
cover-charge argument. Whether it holds on a raw API, where no third-party
scaffolding sits in the prompt, is untested. **Do not generalise this to the
corpus finding**: the corpus median of 1,879 is an `o200k_base` count of catalog
JSON, which is a different measurement than a Cursor-tokenised prompt.

### Open
- The floor still conflates the provider's own system prompt with the surface's
  catalog. A zero-tool control (same path, empty `custom_tools`) would separate
  them and give `floor(A) - floor(0)` as A's true catalog cost on this
  tokenizer. Not built unasked; one flag away if wanted.
- Both figures are single measurements, not repeated.

## 2026-08-15: Human ruling — subtract the Cursor baseline by default (DERIVED table)
### SUPERSEDED by the reversal above. Kept for the audit trail; the code is gone.

Human asked whether the grid could subtract Cursor's baseline token usage to
give a more accurate picture, was shown the objection below in full, and ruled
to do it anyway and log the decision. Recorded here because rule 1 says a number
that was not measured is not data, and this table backs public claims.

### The objection, as put before the ruling
1. **A flat baseline does not fit the measurements.** Subtracting the cheapest
   run (17,245) leaves Surface B an implied per-call cost ranging from **0 to
   6,011 tokens** across the grid — a 60x spread. A fixed-floor-plus-work model
   would leave that roughly constant.
2. **The floor is paid per TURN, not per run.** Every turn resends the
   conversation, so contamination scales with turn count. Surface A takes more
   turns than B on every task here, so subtracting one flat figure
   under-corrects A and **widens the gap in the direction of the thesis**.
3. **The data to do it correctly does not exist on this provider.** Only one
   `usage` event fires per run, so the harness cannot observe turn counts — the
   multiplier the correction would need.
4. **Precedent in this repo.** Gemini cache hits raised the identical
   temptation, and the standing decision, written into `harness.py`, is
   "Reported, not deducted: a cached catalog is a cheaper catalog, not a smaller
   one." A scaffolded run is likewise a more expensive run, not a smaller one.

### What was implemented
- The measured table is unchanged and still prints first. The subtraction lands
  in a **separate table headed `DERIVED`**, carrying "NOT A MEASUREMENT. No API
  reported these numbers" and the bias warning in the output itself, so the
  caveat cannot be separated from the figures by copy-paste.
- Each derived row prints its **raw** value beside it.
- `runs/` is never written with adjusted figures. The cache stays raw, so the
  subtraction can be undone or redone with a better baseline at any time.
- Baseline defaults to the cheapest run in the grid — measured, but circular,
  since it is drawn from the data being corrected. `--baseline-tokens N` accepts
  a figure from a dedicated control run, which would be sounder.
  `--no-derived` suppresses the table entirely.

### Artifacts the ruling produces, recorded for the record
With a 17,245 baseline:
- **Surface B, task 2 -> 0 tokens.** The table asserts B scheduled a meeting and
  sent an invite for nothing.
- **Surface B, task 5 -> 114 tokens.** Task 5 is the three-person, 60-minute,
  room-booked, invite-sending run *with an injected 503*.
- **Task 3's A/B ratio moves from 5.0x raw to 42.1x derived.** That single
  change is larger than any effect the surfaces themselves produced, and it
  moves in the direction the talk argues.

If any derived figure is quoted publicly, the per-turn point is the one an
informed critic will raise first.

### Measured incidentally: the Anaconda env is broken independently of this work
`import numpy` segfaults (exit 139) on `/opt/anaconda3/bin/python`, which is why
`matplotlib` and `google.genai` do too. numpy's dist-info is dated Dec 2024,
months before any SDK was installed for this project, so this is pre-existing
and not caused by the demo. Consequence: **`03_make_charts.py` currently runs on
neither interpreter** — matplotlib is missing on 3.9.6 and segfaults on 3.12.7.
The PNGs in `charts/` date from 2026-08-09 and cannot presently be regenerated.

## 2026-08-26: Public-share prep — rename demo dir, drop sprint language

### Applied
- Renamed `weekend2-demo/` → `demo/` (`git mv -k`; the already-deleted `.json`
  run rows stayed as deletions, the current `.jsonl` rows moved as untracked).
- Rewrote path and sprint wording in `AGENTS.md`, `demo/README.md`,
  `04_cover_charge.py`, `03_make_charts.py`, `01_collect_catalogs.py`,
  `data_dictionary.md`, `methods_note_template.md`, `wrapper_checklist.md`,
  `.cursor/rules/demo-fairness.mdc`, `MANIFEST.md`, and this log. Historical
  log entries now point at `demo/` so a public clone matches the tree.
- Added a root `README.md` and `.env.example`. Removed the personal canvas
  path from `MANIFEST.md`.

### Left alone, deliberately
- `data/raw/` — two catalogs mention "weekend" inside third-party tool
  descriptions. Testimony; not edited.
- Calendar-world "Sunday meetings" in this log (task-6 exclusion) — domain
  content, not sprint language.
- No `LICENSE` added. Copyright choice is human territory.
- Methods-note placeholders still unfilled (rule 3).

### Verified
- Repo-wide search for `weekend` / `weekend1` / `weekend2` outside `data/raw/`
  hits only this entry and the README note about those two raw files.
