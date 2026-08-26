# The Attention Economy of APIs

Empirical work behind the keynote of the same name: a measurement study of
public MCP server tool catalogs, plus a recorded demo that runs the same
calendar tasks through two tool-surface designs.

## What's in this repo

| Path | What it is |
|---|---|
| `01_collect_catalogs.py` | Resumable crawler. Handshake public MCP servers, save tool lists. |
| `02_count_tokens.py` | Token-cost each catalog (`tiktoken` `o200k_base`). Writes `data/results.csv`. |
| `03_make_charts.py` | Histograms from `data/results.csv` into `charts/`. |
| `04_cover_charge.py` | Tokenizer-true cover charge of the two demo surfaces. Stdout only. |
| `data/raw/` | Collected catalogs. Treat as testimony: append, never edit. |
| `data/results.csv` | Derived per-server measurements. Regenerate; don't patch. |
| `data/collect_log.csv` | Append-only attempt log. |
| `demo/` | Simulated calendar world, Surface A (28 endpoint tools), Surface B (6 task tools), harness, scored runs, transcripts. |
| `data_dictionary.md` | Field definitions, written before collection. |
| `wrapper_checklist.md` | Pre-registered rule for wrapper vs task-oriented labels. |
| `methods_note_template.md` | Methods & limitations template. Fill by hand; do not invent numbers. |
| `BUILDLOG.md` | Work log and verification trail. Read before quoting a number. |
| `MANIFEST.md` | Inventory of artifacts used for the talk. |

Surface A is a competent REST-shaped wrapper. Surface B names tools after
outcomes and keeps choreography inside the tools. Same world, same tasks, same
model. The comparison is the demo.

## Setup

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env   # then fill in keys for whichever provider you will call
```

The crawler and token counter need `requests` and `tiktoken`. Charts need
`matplotlib`. The demo harness also needs one of: `anthropic`, `google-genai`,
or `cursor-sdk`, depending on `--provider`.

This machine has no single interpreter that runs everything (Anaconda 3.12
segfaults on numpy/matplotlib/google-genai; system 3.9 cannot install
`cursor-sdk`). Spell the interpreter out. See `AGENTS.md` for the verified
local table.

## Corpus study

```bash
python3 01_collect_catalogs.py 250    # crawl (resumable; skips servers already saved)
python3 02_count_tokens.py            # rebuild results.csv
python3 04_cover_charge.py            # demo surface cover charges
```

Keep the crawler polite: sleeps, timeouts, resume logic, and the User-Agent
contact line stay. Do not re-fetch servers that already succeeded. Dedupe in
analysis (`02_count_tokens.py`), never silently at collection time.

## Demo pair

```bash
python3 demo/harness.py --variant a --task 1 --mock    # plumbing, no API
python3 demo/harness.py --variant a --task 3           # live, surface A
python3 demo/harness.py --variant b --task 3           # same task, surface B
python3 demo/harness.py --all --resume                 # grid; reuse completed runs
```

Details, fairness doctrine, and provider notes: [`demo/README.md`](demo/README.md).

## Data handling

Missing numbers stay missing. `data/raw/` is not cleaned up. Derived files are
disposable. The methods note is filled by the person whose name is on the talk.

Two catalog files mention "weekend" inside third-party tool descriptions
(`data/raw/World_Monitor.json`, `data/raw/ai.dynamicfeed_dynamic-feed.json`).
Those strings are part of the collected evidence and were not edited.
