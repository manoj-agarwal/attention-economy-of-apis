# Methods & Limitations (fill in Sunday, ~30 minutes)

Snapshot taken **[DATE]**, from the official MCP Registry
(registry.modelcontextprotocol.io, API v0), pages fetched in registry order until
**[N_ENTRIES]** unique names were seen (deduped by canonical reverse-domain name).

Of those, **[N_REMOTE]** advertised a remote endpoint; the MCP handshake succeeded
and returned a tool list for **[N_MEASURED]** servers (full attempt log:
`data/collect_log.csv`). Servers that are local-only, require authentication, or
speak only the legacy SSE transport are therefore **not represented** — this sample
covers "servers whose catalogs are publicly observable," and results should be read
with that lean in mind.

Token counts use tiktoken `o200k_base` over a single serialization recipe (compact
JSON, sorted keys, unicode preserved) applied identically to every server; the
recipe and code are published in this repository. Counts were spot-validated against
Anthropic's token-counting endpoint on **[N_VALIDATION]** servers (mean deviation
**[X]%**). Because model providers wrap tool definitions in additional formatting
before models see them, all reported costs are **floor values** — true costs run higher.

The popular-slice lens uses PulseMCP's estimated weekly visitor counts as of
**[DATE]**; these are third-party estimates, used for ranking only.

Wrapper classification was performed by a single rater (**[YOU]**) on a random
subsample of 50 servers (seed **[SEED]**) using the pre-registered rule in
`wrapper_checklist.md`; all 50 labels are published in `data/labels.csv` for
re-rating.

Ten servers were verified end-to-end by hand (raw file vs. CSV row) on **[DATE]**;
**[ANY DISCREPANCIES]**.

Known limitations, in one place: observability bias (above); single-rater labels;
snapshot of a fast-moving ecosystem; floor-value token counts; top-level-only
parameter description stats. Raw data frozen in `data/` under **[FOLDER/TAG NAME]**.
