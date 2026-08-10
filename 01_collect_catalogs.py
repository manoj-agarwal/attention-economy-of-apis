#!/usr/bin/env python3
"""Collect tool catalogs from the most popular public MCP servers.

Usage:
  python 01_collect_catalogs.py [max_servers]
  python 01_collect_catalogs.py [max_servers] --retry-failed

Fetches the full server index from PulseMCP, sorts by github_stars
descending, and attempts the MCP handshake (initialize ->
notifications/initialized -> tools/list) over the streamable-HTTP
transport for the top N servers. Saves raw tool lists to data/raw/.
Every attempt (success or failure) is appended to data/collect_log.csv.

Resume-safe: servers whose raw file already exists in data/raw/ are skipped.

--retry-failed re-attempts only servers whose most recent log status is "error".
"""
import argparse
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

PULSEMCP_API = "https://api.pulsemcp.com/v0beta/servers"
PROTOCOL_VERSION = "2025-06-18"
USER_AGENT = "catalog-cost-study/0.1 (research; put-your-contact-here)"
TIMEOUT = 20
SLEEP_BETWEEN_SERVERS = 0.4

RAW_DIR = Path("data/raw")
LOG_PATH = Path("data/collect_log.csv")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_pulsemcp_top(max_servers):
    """Fetch all servers from PulseMCP, yield top N by github_stars."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    all_servers = []
    offset = 0
    page_size = 200
    print("Fetching PulseMCP server index...", end="", flush=True)
    while True:
        resp = session.get(PULSEMCP_API,
                           params={"count_per_page": page_size, "offset": offset},
                           timeout=30)
        if resp.status_code == 410:
            time.sleep(1)
            offset += page_size
            continue
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("servers") or []
        if not batch:
            break
        all_servers.extend(batch)
        if len(all_servers) % 2000 < page_size:
            print(f" {len(all_servers)}", end="", flush=True)
        if not data.get("next"):
            break
        offset += page_size
        time.sleep(0.3)
    print(f" {len(all_servers)} total.")

    with_remotes = [s for s in all_servers if first_remote_url(s)]
    with_remotes.sort(key=lambda s: s.get("github_stars") or 0, reverse=True)
    top_stars = (with_remotes[0].get("github_stars") or 0) if with_remotes else 0
    cut_stars = (with_remotes[min(max_servers, len(with_remotes)) - 1].get("github_stars") or 0) if with_remotes else 0
    print(f"Servers with remotes: {len(with_remotes)}.  "
          f"Top {max_servers} by github_stars (range {top_stars} -> {cut_stars}).")

    seen = set()
    for srv in with_remotes[:max_servers]:
        name = srv.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        yield {"name": name, "entry": srv}


def first_remote_url(srv):
    """Return (url, transport_type) for the first advertised remote, else None."""
    for remote in srv.get("remotes") or []:
        url = remote.get("url") or remote.get("url_direct")
        if url:
            ttype = (remote.get("type") or remote.get("transport_type")
                     or remote.get("transport") or "")
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


def load_failed_servers():
    """Return names of servers whose most recent log status is 'error'."""
    if not LOG_PATH.exists():
        return set()
    latest = {}
    with LOG_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            latest[row["name"]] = row["status"]
    return {name for name, status in latest.items() if status == "error"}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("max_servers", nargs="?", type=int, default=250,
                        help="top N most-popular servers to attempt (default: 250)")
    parser.add_argument("--retry-failed", action="store_true",
                        help="re-attempt only servers whose most recent log status is 'error'")
    return parser.parse_args()


def main():
    args = parse_args()
    retry_set = load_failed_servers() if args.retry_failed else None
    if args.retry_failed:
        print(f"Retry-failed mode: {len(retry_set)} servers to re-attempt")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    new_log = not LOG_PATH.exists()
    ok = fail = skipped = resumed = 0
    with LOG_PATH.open("a", newline="", encoding="utf-8") as logf:
        log = csv.writer(logf)
        if new_log:
            log.writerow(["fetched_at", "name", "url", "status", "n_tools", "error"])
        for item in get_pulsemcp_top(args.max_servers):
            name, srv = item["name"], item["entry"]

            if retry_set is not None and name not in retry_set:
                continue

            raw_path = RAW_DIR / f"{safe_filename(name)}.json"
            if raw_path.exists():
                resumed += 1
                continue

            remote = first_remote_url(srv)
            if not remote:
                skipped += 1
                log.writerow([now_iso(), name, "", "skipped_no_remote", "", ""])
                continue
            url, _ = remote
            try:
                tools = mcp_tools_list_with_retry(url)
                out = {"name": name, "source_url": url, "fetched_at": now_iso(),
                       "description": srv.get("short_description") or "",
                       "github_stars": srv.get("github_stars"),
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
    print(f"\nDone. collected={ok} failed={fail} skipped_no_remote={skipped} resumed={resumed}")
    print(f"Raw catalogs in {RAW_DIR}/, full log in {LOG_PATH}")
    if ok < 100:
        print("CHECKPOINT: under 100 catalogs — remember the Saturday-lunch pivot rule.")


if __name__ == "__main__":
    main()
