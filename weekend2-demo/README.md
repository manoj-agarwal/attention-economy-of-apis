# Weekend 2 Starter Kit — The Demo Pair

**Goal:** the same agent, the same simulated calendar world, the same tasks — through
two different tool surfaces:

- **Surface A** — a competent 1:1 endpoint wrapper (28 tools, REST-shaped, honest but terse)
- **Surface B** — a task-oriented surface (6 tools named after outcomes)

You record the difference. The token meter is the show.

## Two AIs are in play this weekend — don't conflate them

1. **The editor's agent (Cursor):** writes and fixes code in this repo. Pick any
   model you like in Cursor's model picker; it is a construction worker, not a
   test subject.
2. **The measured agent (inside `harness.py`):** the model called via API during
   runs. This one is the experiment. Pin it (`--model`, default
   `claude-sonnet-4-6`) and change *nothing* between A and B runs — same model,
   same tasks, same seed — or the comparison stops meaning anything.

## Quickstart

```bash
pip install anthropic            # only dependency for live runs
export ANTHROPIC_API_KEY=...     # key for the MEASURED agent (not Cursor)

python harness.py --variant a --task 1 --mock    # plumbing test, no API needed
python harness.py --variant a --task 3           # live run, surface A, hero task
python harness.py --variant b --task 3           # same task, surface B
python harness.py --all                          # full 6x2 grid, one run each, table at the end
```

Default measured model: claude-sonnet-4-6. A full 6x2 grid costs roughly a few
dollars; run the grid before recording takes.

## Driving this with Cursor

The rules in `../AGENTS.md` apply everywhere; `.cursor/rules/demo-fairness.mdc`
auto-attaches whenever the agent touches files in this folder. The one that
matters most: **the surfaces are frozen** — fixes may touch `harness.py`,
`tasks.py` checks, and world plumbing, but any change to either surface's tools,
descriptions, schemas, or dispatch needs your explicit approval first.

Saturday shakedown prompt (Agent mode):

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

## Recording (Sunday)

- Record from a **plain terminal window**, not the editor's embedded panel — the
  frame should contain the meter and nothing else. 22pt+ font, dark theme,
  window about 1280x720. QuickTime or OBS, screen-region capture.
- Three takes per clip; keep every raw take.
- Clip 1 (cold open): `--variant a --task 3`. Let the meter tell the story.
- Clip 2 (payoff): `--variant b --task 3`.
- Also capture: the final table from `--all` for the summary slide, and one
  `--variant a --task 5` run for the error-tax beat if it lands well.

## The gate

Two usable clips plus the 6x2 table by Sunday dinner — or the fallback cold open
(corpus findings + a real public GitHub-issue failure) goes in the talk instead.
Footage first, polish never before Sunday.
