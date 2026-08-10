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
