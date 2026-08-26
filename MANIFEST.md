# Deck bundle manifest

Assembled 2026-08-15 for the slide deck. Every path is relative to the repo
root. Row counts exclude CSV headers. "Last commit" is the most recent commit
that touched the file; `uncommitted` means the working tree is ahead of git.

Repo HEAD when this was written: `c9a3032`.

**Read `BUILDLOG.md` before quoting any number here.** Several figures in the
demo half of this study carry caveats that change what they can support.

---

## 1. Corpus study — ready

| Artifact | Path | Size | Last commit |
|---|---|---|---|
| Per-server results | `data/results.csv` | 162 rows | `8312ed0` |
| Full attempt log | `data/collect_log.csv` | 621 rows | `8312ed0` |
| Raw catalogs | `data/raw/` | 162 JSON files | `8312ed0` |
| Charts | `charts/` | 2 PNG | 2026-08-09 |
| Field definitions | `data_dictionary.md` | 25 lines | `add2ae0` |

`results.csv` columns: `name, source_url, fetched_at, n_tools, catalog_tokens,
median_tool_tokens, largest_tool_tokens, pct_params_described,
any_enum_constraint, longest_description_chars, count_method`.

**On "post-freeze":** no freeze event is recorded anywhere in this repo. The
word "frozen" appears only in `data_dictionary.md` (about the schema),
`demo/README.md` (about the demo surfaces), and as an unfilled
placeholder in the methods note. `results.csv` and `collect_log.csv` have both
been untouched since `8312ed0`, which is the closest thing to a freeze that
exists. Confirm this is what you meant before the deck cites a frozen snapshot.

**Charts cannot currently be regenerated.** `03_make_charts.py` runs on neither
interpreter: `matplotlib` is absent on `/usr/bin/python3` and segfaults on
`/opt/anaconda3/bin/python`, where `import numpy` itself dies. That breakage is
dated Dec 2024 and predates this project. The two PNGs are from 2026-08-09.

## 2. Demo pair — ready, with caveats

| Artifact | Path | Contents |
|---|---|---|
| Scored run rows | `demo/runs/*_task*.jsonl` | 16 cells, 3 samples each (task 10: 1) |
| Provider floor | `demo/runs/floor_*.jsonl` | 2 records (surface A, surface B) |
| Transcripts | `demo/transcripts/` | 55 files |
| Surfaces | `demo/surface_a.py`, `surface_b.py` | 28 tools / 6 tools, frozen |
| Tasks + checks | `demo/tasks.py` | 10 defined, 7 in the grid |

Provider `cursor`, model `claude-sonnet-4-6`, seed 1776, measured 2026-08-15.

**Headline result:** Surface B completed 21 of 21 grid runs; Surface A completed
15 of 21. Reproduces across all three samples.

**Token figures are not quotable as point estimates.** Identical configurations
differed by up to 62% between runs, and this provider adds ~5–6k tokens of its
own scaffolding per turn. Not comparable to a raw-API run or to the corpus
median. Call counts are the stable measurement (median 3% variation).

## 3. Narration source — the takes that matter

Three samples per cell unless noted. Newest file per cell is the one with tool
outputs recorded.

| Task | Surface A | Surface B |
|---|---|---|
| 3 (hero: 3 people, room, invites) | 4 transcripts | 3 transcripts |
| 5 (same + injected 503) | 4 transcripts | 4 transcripts |
| 8 (cancel 1:1 + notify) | 3 transcripts | 3 transcripts |
| 9 (two 1:1s + invites) | 3 transcripts | 3 transcripts |

**Transcripts written before 2026-08-15 13:15 do not contain tool outputs.**
Until then the harness recorded only the model's calls, so no run that provoked
the 503 ever captured it. Fixed in `harness.py` (`write_turn`, and the Cursor
session now folds the SDK's `result` field into each event). Task 5 was re-run
on both surfaces afterwards specifically to capture it.

Files that contain the payloads, verified:

- `demo/transcripts/a_task5_1786826112.jsonl` — Surface A, contains
  `book_room -> {"error": "503 Service Unavailable"}`
- `demo/transcripts/b_task5_1786826189.jsonl` — Surface B, same
  injected failure, returns
  `{"scheduled": ..., "invites_sent": 2, "note": "Room Aurora booked."}`

The contrast is the beat: Surface A hands the model a bare status code with no
guidance; Surface B retries inside the tool, and **the model is never told the
infrastructure failed.** Note that Surface B's success note overwrites its own
"booked after one automatic retry (transient 503)" string, so B's transcript
carries no trace of the retry at all — that is the frozen surface's existing
behaviour, not an artefact of the fix.

Extract payloads with:

```bash
/opt/anaconda3/bin/python - <<'PY'
import json
p = "demo/transcripts/a_task5_1786826112.jsonl"
for line in open(p):
    for r in json.loads(line).get("tool_results") or []:
        print(r["name"], "->", json.dumps(r["output"])[:300])
PY
```

## 4. Narrative and fairness sources

| Artifact | Path | Size | Last commit |
|---|---|---|---|
| Build log | `BUILDLOG.md` | 1,401 lines | `c9a3032` (+ uncommitted) |
| Rating rule | `wrapper_checklist.md` | 44 lines | `add2ae0` |
| Methods note | `methods_note_template.md` | 34 lines | `add2ae0` |

`BUILDLOG.md` carries the fairness material: registered predictions for tasks 9
and 10 with their falsifiers and outcomes, the reversed subtract-the-baseline
ruling with the objection that preceded it, the excluded tasks and their
reasons, and the sample-to-sample variance that retired several earlier claims.

## 5. NOT AVAILABLE

**`data/labels.csv` — does not exist.** The 50-server wrapper rating has not
been performed and no seed has been chosen. `wrapper_checklist.md` holds the
pre-registered rule, so the procedure is ready; the labels are not. The methods
note already promises this file in its text, so that sentence is currently
false.

**The methods note is an unfilled template.** Every figure is a placeholder:
`[DATE]`, `[N_ENTRIES]`, `[N_REMOTE]`, `[N_MEASURED]`, `[N_VALIDATION]`, `[X]%`,
`[YOU]`, `[SEED]`, `[FOLDER/TAG NAME]`, `[ANY DISCREPANCIES]`. Filling it is
human-only work per the repo rules and has deliberately not been done.

**There is no PDF report in this repository.** The written report lived in a
local Cursor canvas and was not copied here.

**No Anthropic-provider numbers exist.** `ANTHROPIC_API_KEY` was never set, so
the pinned `claude-sonnet-4-6` was only ever reached through the Cursor plan,
with that provider's scaffolding included. There is also no per-turn token
curve, because this provider emits one usage event per run — so no footage of a
climbing meter exists either.
