#!/usr/bin/env python3
"""The demo harness: one agent loop, two surfaces, a live token meter.

Usage:
  python harness.py --variant a --task 3            # live run (needs ANTHROPIC_API_KEY)
  python harness.py --variant b --task 3 --mock     # plumbing test, no network
  python harness.py --all                           # 6x2 grid, table at the end

The meter is the show: cover charge first, then a running total per turn.
Transcripts land in transcripts/ as JSONL. Nothing here edits world state
except through the surface dispatchers - same primitives for both variants.
"""
import argparse, json, os, sys, time
from pathlib import Path

from calendar_world import World
import surface_a, surface_b
from tasks import TASKS

MODEL_DEFAULT = "claude-sonnet-4-6"
MAX_TURNS = 25
TRANSCRIPT_DIR = Path(__file__).resolve().parent / "transcripts"

def est_tokens(s):  # display-only estimate for the cover-charge line
    return max(1, round(len(s) / 3.5))

def meter(turn, label, tin, tout, calls):
    print(f"  [meter] turn {turn:>2} | {label:<28s} | tokens {tin:>7,} in / {tout:>6,} out | tool calls {calls}")

class MockClient:
    """Offline stand-in that exercises the full loop: 2 tool calls, then text."""
    def __init__(self, variant):
        self.script = ([("search_contacts", {"query": "priya"}), ("get_free_busy",
                        {"contact_id": "priya", "time_min": "2026-08-24T00:00:00Z",
                         "time_max": "2026-08-29T00:00:00Z"})] if variant == "a"
                       else [("find_meeting_time", {"attendees": ["Priya"]}),
                             ("schedule_meeting", {"attendees": ["Priya"], "topic": "Q3 roadmap"})])
        self.i = 0
    def create(self, **kw):
        if self.i < len(self.script):
            name, args = self.script[self.i]; self.i += 1
            return {"stop_reason": "tool_use", "usage": {"input_tokens": 1200 + 300*self.i,
                    "output_tokens": 60},
                    "content": [{"type": "tool_use", "id": f"mock_{self.i}", "name": name, "input": args}]}
        return {"stop_reason": "end_turn", "usage": {"input_tokens": 1500, "output_tokens": 40},
                "content": [{"type": "text", "text": "(mock) Done - plumbing verified."}]}

def to_plain(resp):
    """Normalize SDK response objects or mock dicts to one plain shape."""
    if isinstance(resp, dict):
        return resp
    out = {"stop_reason": resp.stop_reason,
           "usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens},
           "content": []}
    for b in resp.content:
        if b.type == "text":
            out["content"].append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            out["content"].append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    return out

def run(variant, task_id, model, mock=False, quiet=False):
    surface = surface_a if variant == "a" else surface_b
    task = TASKS[task_id]
    world = World(inject_room_failure=task["failure_switch"])
    catalog = json.dumps(surface.TOOLS, separators=(",", ":"), sort_keys=True)
    if not quiet:
        print(f"\n=== variant {variant.upper()} | task {task_id}: {task['prompt'][:60]}...")
        print(f"  [meter] cover charge: {len(surface.TOOLS)} tools, ~{est_tokens(catalog):,} tokens (est)")
    if mock:
        client = MockClient(variant)
        call = lambda msgs: client.create()
    else:
        import anthropic
        client = anthropic.Anthropic()
        call = lambda msgs: client.messages.create(
            model=model, max_tokens=1024, tools=surface.TOOLS,
            system="You are a scheduling assistant. Use the tools to actually complete "
                   "the user's request; don't just describe what you would do.",
            messages=msgs)
    msgs = [{"role": "user", "content": task["prompt"]}]
    tin = tout = calls = 0
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    tpath = TRANSCRIPT_DIR / f"{variant}_task{task_id}_{int(time.time())}.jsonl"
    t0 = time.time()
    for turn in range(1, MAX_TURNS + 1):
        resp = to_plain(call(msgs))
        tin += resp["usage"]["input_tokens"]; tout += resp["usage"]["output_tokens"]
        with tpath.open("a") as fh:
            fh.write(json.dumps(resp) + "\n")
        tools_used = [b for b in resp["content"] if b["type"] == "tool_use"]
        if resp["stop_reason"] == "tool_use" and tools_used:
            results = []
            for b in tools_used:
                calls += 1
                out = surface.dispatch(world, b["name"], b["input"])
                if not quiet:
                    meter(turn, b["name"], tin, tout, calls)
                results.append({"type": "tool_result", "tool_use_id": b["id"], "content": out})
            msgs.append({"role": "assistant", "content": resp["content"]})
            msgs.append({"role": "user", "content": results})
            continue
        final = " ".join(b["text"] for b in resp["content"] if b["type"] == "text")
        if not quiet:
            meter(turn, "(final answer)", tin, tout, calls)
            print(f"  agent: {final[:200]}")
        break
    ok = bool(task["check"](world))
    secs = time.time() - t0
    verdict = "SUCCESS" if ok else "FAIL"
    if mock:
        verdict += " (mock: verdict not meaningful)"
    if not quiet:
        print(f"  RESULT: {verdict} | {tin+tout:,} total tokens | {calls} tool calls | {secs:.0f}s")
    return {"variant": variant, "task": task_id, "ok": ok, "tokens": tin + tout,
            "tin": tin, "tout": tout, "calls": calls, "secs": round(secs)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["a", "b"])
    ap.add_argument("--task", type=int, choices=sorted(TASKS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--model", default=MODEL_DEFAULT)
    args = ap.parse_args()
    if args.all:
        rows = [run(v, t, args.model, mock=args.mock, quiet=False)
                for t in sorted(TASKS) for v in ("a", "b")]
        print("\n=== SUMMARY (paste this into the talk repo) ===")
        print(f"{'task':>4} | {'A ok':>5} {'A tokens':>9} {'A calls':>7} | {'B ok':>5} {'B tokens':>9} {'B calls':>7}")
        for t in sorted(TASKS):
            a = next(r for r in rows if r["task"] == t and r["variant"] == "a")
            b = next(r for r in rows if r["task"] == t and r["variant"] == "b")
            print(f"{t:>4} | {str(a['ok']):>5} {a['tokens']:>9,} {a['calls']:>7} |"
                  f" {str(b['ok']):>5} {b['tokens']:>9,} {b['calls']:>7}")
        return
    if not (args.variant and args.task):
        ap.error("either --all, or both --variant and --task")
    run(args.variant, args.task, args.model, mock=args.mock)

if __name__ == "__main__":
    main()
