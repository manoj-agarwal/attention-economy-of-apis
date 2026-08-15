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
