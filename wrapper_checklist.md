# Wrapper Test — scoring sheet (~30 min sessions)

**Purpose:** classify a random 50 of the measured servers as endpoint-wrappers or
task-oriented designs — using a fixed rule, not a vibe. Publish this sheet AND your
50 labels (`data/labels.csv`) so anyone can re-score you.

## Procedure

1. Draw 50 server names at random from `data/results.csv` (script or spreadsheet;
   record the random seed in the methods note).
2. For each server, open its raw file in `data/raw/` and read the tool names,
   descriptions, and input parameters. 3–4 minutes per server. First pass, no agonizing.
3. Score the signals below, apply the decision rule, record one label per server in
   `data/labels.csv` with columns: `name, S1, S2, S3, S4, label, note`.

## Signals (score each 0 or 1)

- **S1 — CRUD families.** Tool names form create/get/update/delete/list sets around
  resources (`create_ticket`, `get_ticket`, `update_ticket`...). Score 1 if you count
  three or more full or near-full families.
- **S2 — ID relay.** Tools require internal identifiers (record IDs, UUIDs) that can
  only be obtained by first calling other tools. Score 1 if common workflows clearly
  need 3+ chained calls.
- **S3 — Endpoint prose.** Descriptions read like pasted API reference ("Returns a
  paginated list of X objects") rather than task guidance ("Use this when the user
  wants..."). Score 1 if that's the dominant style.
- **S4 — Mirror count.** The tool count is suspiciously close to the underlying
  API's endpoint count, where the underlying API is known. Score 1 if plausibly 1:1.
  (Skip if unknown — do not guess.)

## Decision rule

- **wrapper** — S1 = 1 AND (S2 = 1 OR S3 = 1); or total score ≥ 3.
- **task-oriented** — total score ≤ 1 AND tool names describe outcomes
  (verbs a user would say: `schedule_meeting`, `summarize_thread`).
- **mixed** — clear task-oriented tools sitting alongside at least one full CRUD family.
- **unclear** — can't tell from the catalog alone (say why in `note`).

## Honesty rules

- One rater (you). Mitigation: this published rule + published labels invite re-rating.
- Don't peek at `catalog_tokens` while labeling — classify from the design, not the
  cost, or you'll bias the very correlation you want to report.
- Record every judgment call in `note`, ugly ones especially.
