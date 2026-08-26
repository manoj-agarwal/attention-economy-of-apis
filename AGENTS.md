# Agent instructions — API Attention Study

This repo contains the empirical work behind the keynote "The Attention Economy of
APIs": a measurement study of public MCP server tool catalogs (root-level scripts)
and a recorded demo pair comparing two tool-surface designs (demo/).
You are the research assistant. The human owns every judgment call.

## Layout

- Repo root — registry crawler, token counter, chart scripts, cover-charge
  script, `data/`, `charts/`, data dictionary, wrapper checklist, methods note.
- `demo/` — simulated calendar world, Surface A (endpoint wrapper),
  Surface B (task tools), harness with token meter, tasks, transcripts/.
- `BUILDLOG.md` — running record of delegated work and human verification.

## Commands

**No single interpreter runs everything.** Always spell the interpreter out in
full; bare `python` / `pip` resolve to Anaconda and bare `python3` resolves to
the 3.9 one, so neither says what you mean. Verified 2026-08-15:

| work | interpreter |
|---|---|
| crawler, token counter, cover charge | either |
| `03_make_charts.py` | **neither, currently** |
| harness `--provider anthropic` | either |
| harness `--provider gemini` | `/usr/bin/python3` only |
| harness `--provider cursor` | `/opt/anaconda3/bin/python` only |

- `/usr/bin/python3` is 3.9.6: has anthropic + google-genai, no matplotlib, and
  cannot install `cursor-sdk` (needs >=3.10).
- `/opt/anaconda3/bin/python` is 3.12.7: has anthropic + cursor-sdk, but
  `import google.genai` and `import matplotlib` both segfault (exit 139)
  because `import numpy` segfaults there. That breakage is dated Dec 2024 and
  predates any SDK installed for this project — it is a pre-existing broken
  Anaconda env, not something the demo did.
- So charts cannot be regenerated on either interpreter right now. The PNGs in
  `charts/` date from 2026-08-09. Fix the env before trusting `03_make_charts.py`.

```bash
/usr/bin/python3 -m pip install -r requirements.txt
/usr/bin/python3 01_collect_catalogs.py 250          # crawl (resumable)
/usr/bin/python3 02_count_tokens.py                  # rebuild results.csv
/usr/bin/python3 04_cover_charge.py                  # surface cover charges

# demo - match the interpreter to the provider, per the table above
/opt/anaconda3/bin/python demo/harness.py --provider cursor --all --resume
/usr/bin/python3 demo/harness.py --provider gemini --variant a --task 3
/opt/anaconda3/bin/python demo/harness.py --variant a --task 3   # anthropic
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
