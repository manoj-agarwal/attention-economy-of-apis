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
