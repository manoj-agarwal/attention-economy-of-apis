#!/usr/bin/env python3
"""Collect tool catalogs from public MCP servers listed in the official registry.

Usage: python 01_collect_catalogs.py [max_servers]

For every registry entry that advertises a remote endpoint, performs the MCP
handshake (initialize -> notifications/initialized -> tools/list) over the
streamable-HTTP transport and saves the raw tool list to data/raw/.
Every attempt (success or failure) is appended to data/collect_log.csv.
"""
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REGISTRY = "https://registry.modelcontextprotocol.io/v0/servers"
PAGE_LIMIT = 100
PROTOCOL_VERSION = "2025-06-18"
USER_AGENT = "catalog-cost-study/0.1 (research; put-your-contact-here)"
TIMEOUT = 20
SLEEP_BETWEEN_SERVERS = 0.4

RAW_DIR = Path("data/raw")
LOG_PATH = Path("data/collect_log.csv")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_registry_pages(max_servers):
    """Yield deduped server entries from the registry, defensively parsed."""
    seen = set()
    cursor = None
    yielded = 0
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    while yielded < max_servers:
        params = {"limit": PAGE_LIMIT}
        if cursor:
            params["cursor"] = cursor
        resp = session.get(REGISTRY, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        entries = data.get("servers") or data.get("data") or []
        if not entries:
            return
        for entry in entries:
            # Entries may be flat, or nested under a "server" key.
            srv = entry.get("server", entry) if isinstance(entry, dict) else {}
            name = srv.get("name") or entry.get("name")
            if not name or name in seen:
                continue
            seen.add(name)
            yield {"name": name, "entry": srv}
            yielded += 1
            if yielded >= max_servers:
                return
        meta = data.get("metadata") or data.get("meta") or {}
        cursor = meta.get("next_cursor") or meta.get("nextCursor")
        if not cursor:
            return


def first_remote_url(srv):
    """Return (url, transport_type) for the first advertised remote, else None."""
    for remote in srv.get("remotes") or []:
        url = remote.get("url")
        if url:
            ttype = remote.get("type") or remote.get("transport_type") or ""
            return url, ttype
    return None


def parse_jsonrpc_response(resp):
    """Return a list of JSON-RPC messages from a plain-JSON or SSE response."""
    ctype = resp.headers.get("content-type", "")
    body = resp.text or ""
    if "text/event-stream" in ctype or body.lstrip().startswith(("event:", "data:")):
        messages = []
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                if payload:
                    try:
                        messages.append(json.loads(payload))
                    except json.JSONDecodeError:
                        pass
        return messages
    try:
        return [resp.json()]
    except json.JSONDecodeError:
        return []


def find_result(messages, msg_id):
    for msg in messages:
        if isinstance(msg, dict) and str(msg.get("id")) == str(msg_id) and "result" in msg:
            return msg["result"]
    return None


def mcp_tools_list(url):
    """Perform the MCP handshake against a remote server; return the tools list."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
    })
    init = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "catalog-cost-study", "version": "0.1.0"},
        },
    }
    resp = session.post(url, json=init, timeout=TIMEOUT)
    resp.raise_for_status()
    session_id = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
    if session_id:
        session.headers["Mcp-Session-Id"] = session_id
    if find_result(parse_jsonrpc_response(resp), 1) is None:
        raise RuntimeError("initialize returned no result")

    session.post(url, json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                 timeout=TIMEOUT)

    tools, cursor = [], None
    for page in range(2, 12):  # up to 10 pages of tools
        params = {"cursor": cursor} if cursor else {}
        resp = session.post(url, json={"jsonrpc": "2.0", "id": page,
                                       "method": "tools/list", "params": params},
                            timeout=TIMEOUT)
        resp.raise_for_status()
        result = find_result(parse_jsonrpc_response(resp), page)
        if result is None:
            raise RuntimeError("tools/list returned no result")
        tools.extend(result.get("tools") or [])
        cursor = result.get("nextCursor")
        if not cursor:
            break
    return tools


def mcp_tools_list_with_retry(url, retries=1):
    """Retry on transient network errors (ConnectionError, Timeout, 503)."""
    for attempt in range(1 + retries):
        try:
            return mcp_tools_list(url)
        except (requests.ConnectionError, requests.Timeout):
            if attempt == retries:
                raise
            time.sleep(2)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 503 and attempt < retries:
                time.sleep(2)
                continue
            raise


def safe_filename(name):
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:180]


def main():
    max_servers = int(sys.argv[1]) if len(sys.argv) > 1 else 250
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    new_log = not LOG_PATH.exists()
    ok = fail = skipped = 0
    with LOG_PATH.open("a", newline="", encoding="utf-8") as logf:
        log = csv.writer(logf)
        if new_log:
            log.writerow(["fetched_at", "name", "url", "status", "n_tools", "error"])
        for item in get_registry_pages(max_servers):
            name, srv = item["name"], item["entry"]
            remote = first_remote_url(srv)
            if not remote:
                skipped += 1
                log.writerow([now_iso(), name, "", "skipped_no_remote", "", ""])
                continue
            url, _ = remote
            try:
                tools = mcp_tools_list_with_retry(url)
                out = {"name": name, "source_url": url, "fetched_at": now_iso(),
                       "registry_description": srv.get("description", ""),
                       "tools": tools}
                path = RAW_DIR / f"{safe_filename(name)}.json"
                path.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                encoding="utf-8")
                ok += 1
                log.writerow([now_iso(), name, url, "ok", len(tools), ""])
                print(f"OK   {name}  ({len(tools)} tools)")
            except Exception as exc:  # noqa: BLE001 - log everything, study continues
                fail += 1
                log.writerow([now_iso(), name, url, "error", "",
                              f"{type(exc).__name__}: {exc}"[:300]])
                print(f"FAIL {name}  {type(exc).__name__}")
            time.sleep(SLEEP_BETWEEN_SERVERS)
    print(f"\nDone. collected={ok} failed={fail} skipped_no_remote={skipped}")
    print(f"Raw catalogs in {RAW_DIR}/, full log in {LOG_PATH}")
    if ok < 100:
        print("CHECKPOINT: under 100 catalogs — remember the Saturday-lunch pivot rule.")


if __name__ == "__main__":
    main()
