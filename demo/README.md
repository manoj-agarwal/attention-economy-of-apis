# Demo pair — two surfaces, one calendar world

**Goal:** the same agent, the same simulated calendar world, the same tasks — through
two different tool surfaces:

- **Surface A** — a competent 1:1 endpoint wrapper (28 tools, REST-shaped, honest but terse)
- **Surface B** — a task-oriented surface (6 tools named after outcomes)

You record the difference. The token meter is the show.

## Two AIs are in play — don't conflate them

1. **The editor's agent (Cursor):** writes and fixes code in this repo. Pick any
   model you like in Cursor's model picker; it is a construction worker, not a
   test subject.
2. **The measured agent (inside `harness.py`):** the model called via API during
   runs. This one is the experiment. Pin it (`--model`, default
   `claude-sonnet-4-6`) and change *nothing* between A and B runs — same model,
   same tasks, same seed — or the comparison stops meaning anything.

## Quickstart

**Pick the interpreter to match the provider** — no single one runs all three,
and bare `python` / `python3` will silently pick the wrong one:

| provider | interpreter | key |
|---|---|---|
| anthropic | either | `ANTHROPIC_API_KEY` |
| gemini | `/usr/bin/python3` (3.9.6) | `GEMINI_API_KEY` |
| cursor | `/opt/anaconda3/bin/python` (3.12.7) | `CURSOR_API_KEY` |

`cursor-sdk` needs Python >=3.10 so it cannot go on 3.9; `google.genai`
segfaults on Anaconda. See `../AGENTS.md` for the full table.

```bash
/opt/anaconda3/bin/python -m pip install anthropic cursor-sdk
export ANTHROPIC_API_KEY=...      # key for the MEASURED agent (not Cursor)

P=/opt/anaconda3/bin/python
$P harness.py --variant a --task 1 --mock    # plumbing test, no API needed
$P harness.py --variant a --task 3           # live run, surface A, hero task
$P harness.py --variant b --task 3           # same task, surface B
$P harness.py --all                          # full 6x2 grid, table at the end
```

`--all --resume` reuses completed runs recorded in `runs/` instead of
re-spending quota, and marks those rows `*`. `runs/` is derived and disposable —
delete it to force a clean grid.

Per-provider notes:

- **gemini** free tier is 5 requests/min *and 20 per day*, and one turn is one
  request. A grid needs 100+, so it cannot finish on the free tier at any
  pacing. The harness paces requests 12s apart (`--min-interval`) and waits out
  per-minute 429s, but refuses to retry a per-day cap.
- **cursor** routes through the caller's Cursor plan, exposing the surfaces as
  custom tools. It has no practical quota ceiling — a full grid is ~10 minutes —
  but **its token numbers are not comparable to the other providers**: Cursor's
  own system prompt adds ~50k input tokens against a surface whose cover charge
  is ~2,000, and only one `usage` event fires per run, so the per-turn meter
  collapses to a single row. Use it for `ok`/`calls`, not for tokens or clips.

Default measured model: claude-sonnet-4-6. A full 6x2 grid costs roughly a few
dollars; run the grid before recording takes.

## Driving this with Cursor

The rules in `../AGENTS.md` apply everywhere; `.cursor/rules/demo-fairness.mdc`
auto-attaches whenever the agent touches files in this folder. The one that
matters most: **the surfaces are frozen** — fixes may touch `harness.py`,
`tasks.py` checks, and world plumbing, but any change to either surface's tools,
descriptions, schemas, or dispatch needs your explicit approval first.

Plumbing prompt (Agent mode):

```
Run harness.py --variant a --task 1 and --variant b --task 1 live. If a success
check misfires, propose fixes to tasks.py or harness.py only - surfaces are
frozen per the fairness rule. Show diffs before applying.
```

Grid prompt:

```
Run harness.py --all with the pinned model. Paste the summary table into
BUILDLOG.md with today's date, flag any task where A succeeded and B failed
(or vice versa), and commit. Do not touch transcripts/.
```

## The files

- `calendar_world.py` — deterministic simulated world: 5 people across 4 timezones,
  seeded busy calendars (seed 1776), 3 bookable rooms, one injectable transient failure.
- `surface_a.py` — 28 endpoint-shaped tools. Fairness rules: accurate schemas,
  truthful descriptions, verbose-but-honest payloads (real APIs return full objects).
  Errors are bare status codes, because that is what real wrappers relay.
- `surface_b.py` — 6 task tools. Choreography, timezone math, retries, and error
  translation live inside the tools, where they are deterministic and free.
- `tasks.py` — 8 tasks with programmatic success checks against world state; 6 run
  in the `--all` grid, and tasks 1 and 6 are excluded with their reasons stated in
  the file and reprinted above the summary table.
  Task 5 flips the failure switch (one transient 503 on room booking).
- `harness.py` — the agent loop, live token meter, JSONL transcripts, results table.
- `transcripts/` — evidence. Never edited, never regenerated in place.

## Fairness doctrine (say this on stage, put it in the repo)

1. Surface A is competent, not sabotaged. Same world, same permissions, same model,
   same turn budget as B. Its cover charge (~2,050 tokens) sits at the measured
   field median — A is a *typical* public server, not a strawman.
2. The backend is simulated and seeded; interface shapes mirror real calendar APIs.
3. Both surfaces, all transcripts, and this doctrine are published. Re-run me.

## Recording

- Record from a **plain terminal window**, not the editor's embedded panel — the
  frame should contain the meter and nothing else. 22pt+ font, dark theme,
  window about 1280x720. QuickTime or OBS, screen-region capture.
- Three takes per clip; keep every raw take.
- Clip 1 (cold open): `--variant a --task 3`. Let the meter tell the story.
- Clip 2 (payoff): `--variant b --task 3`.
- Also capture: the final table from `--all` for the summary slide, and one
  `--variant a --task 5` run for the error-tax beat if it lands well.
