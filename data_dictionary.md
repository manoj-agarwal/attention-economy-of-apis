# Data Dictionary — one row per measured server in `data/results.csv`

Written before collection, frozen for the weekend. If a field must change, note it
in the methods note.

| Field | Type | Definition | How collected |
|---|---|---|---|
| `name` | text | Canonical reverse-domain server name (e.g. `io.github.owner/server`). Doubles as the dedupe key. | Official registry entry |
| `source_url` | text | The remote endpoint the handshake was performed against. | Registry entry (`remotes`) |
| `fetched_at` | timestamp | UTC moment the catalog was collected. Defines the snapshot. | Crawler |
| `n_tools` | integer | Number of tools in the `tools/list` response. | Handshake |
| `catalog_tokens` | integer | Tokens in the full tool list, serialized with the standard recipe (compact JSON, sorted keys, unicode preserved). **The cover charge.** | Script 02 |
| `median_tool_tokens` | integer | Middle value of per-tool token costs; resistant to one monster tool. | Script 02 |
| `largest_tool_tokens` | integer | Cost of the single most expensive tool. | Script 02 |
| `pct_params_described` | percent | Share of top-level input parameters that carry a human-written description. Nested objects not descended into (say so in methods note). | Script 02 |
| `any_enum_constraint` | boolean | Whether any parameter restricts values to a fixed option list — a basic schema-quality signal. | Script 02 |
| `longest_description_chars` | integer | Length of the longest tool description; flags both barren and bloated extremes. | Script 02 |
| `count_method` | text | `tiktoken:o200k_base` (quotable) or `estimate:chars/3.5` (not quotable). | Script 02 |

## Joined later, separate files

| Field | Where | Definition |
|---|---|---|
| `popularity_estimate` | `data/popularity.csv` | Estimated weekly visitors from PulseMCP, where available; enables the "popular slice" lens. |
| `wrapper_label` | `data/labels.csv` | Your manual classification: `wrapper` / `task-oriented` / `mixed` / `unclear`, per `wrapper_checklist.md`, on the random-50 subsample. |
