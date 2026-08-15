# Agent instructions — API Attention Study

This repo contains the empirical work behind the keynote "The Attention Economy of
APIs": a measurement study of public MCP server tool catalogs (weekend1-starter/)
and a recorded demo pair comparing two tool-surface designs (weekend2-demo/).
You are the research assistant. The human owns every judgment call.

## Layout

- `weekend1-starter/` — registry crawler, token counter, chart scripts, data/,
  data dictionary, wrapper checklist, methods note.
- `weekend2-demo/` — simulated calendar world, Surface A (endpoint wrapper),
  Surface B (task tools), harness with token meter, tasks, transcripts/.
- `BUILDLOG.md` — running record of delegated work and human verification.

## Commands

```bash
pip install -r weekend1-starter/requirements.txt
python weekend1-starter/01_collect_catalogs.py 250      # crawl (resumable)
python weekend1-starter/02_count_tokens.py              # rebuild results.csv
python weekend1-starter/03_make_charts.py               # rebuild charts
pip install anthropic
python weekend2-demo/harness.py --variant a --task 3    # live demo run
python weekend2-demo/harness.py --all                   # full 6x2 grid
```

## Non-negotiable rules

1. Never fabricate, interpolate, or "clean up" data. A missing number stays
   missing, because this dataset backs public claims.
2. Treat `data/raw/` as testimony: append or annotate, never edit or delete.
   Derived files (results.csv, charts) are disposable — regenerate, don't patch.
3. Never fill numbers into the methods note or edit its claims. The human does
   that by hand, because their name defends it on stage.
4. Keep the crawler polite: preserve sleeps, timeouts, resume logic, and the
   User-Agent contact line. Never re-fetch servers that already succeeded.
5. Dedupe in analysis, visibly, never silently at collection time.
6. After each work block, append a dated entry to BUILDLOG.md: what you did,
   what you verified, what failed.
7. Stop at declared gates (catalog counts, clip deadlines) and report; the
   human decides pivots.
8. Random seeds, wrapper labels, verification rows, and fairness properties of
   the demo surfaces are human-only territory. Propose; never apply unasked.

## Corrections

When the human corrects you in chat, offer to encode it permanently as a rule in
`.cursor/rules/` using the form "Do X, not Y, because Z" — chat memory does not
survive the session; rules do.
