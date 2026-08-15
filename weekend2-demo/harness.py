#!/usr/bin/env python3
"""The demo harness: one agent loop, two surfaces, a live token meter.

Usage:
  python harness.py --variant a --task 3            # live run (needs ANTHROPIC_API_KEY)
  python harness.py --variant b --task 3 --mock     # plumbing test, no network
  python harness.py --all                           # 6x2 grid, table at the end
  python harness.py --provider gemini --variant a --task 3   # needs GEMINI_API_KEY

The meter is the show: cover charge first, then a running total per turn.
Transcripts land in transcripts/ as JSONL. Nothing here edits world state
except through the surface dispatchers - same primitives for both variants.

Two providers drive the same loop over the same frozen surfaces. Everything
provider-specific is wire format only: how tool declarations are spelled, how
tool results travel back, which field carries a token count. The conversion is
a pure function of a surface's TOOLS list, so it cannot treat A and B
differently - an asymmetry there would bias the experiment invisibly.
"""
import argparse, json, os, sys, time
from pathlib import Path

from calendar_world import World
import surface_a, surface_b
from tasks import TASKS, GRID, EXCLUDED

MODEL_DEFAULT = "claude-sonnet-4-6"
# Free-tier eligible per ai.google.dev/gemini-api/docs/pricing (Standard tier
# reads "Free of charge" for input and output), stable, and the model the
# current function-calling docs use in their own examples. Free-tier siblings
# if this one is rate-limited: gemini-3.5-flash, gemini-3.5-flash-lite,
# gemini-3.1-flash-lite. Pro models are paid-tier only.
GEMINI_MODEL_DEFAULT = "gemini-3.6-flash"
MODEL_DEFAULTS = {"anthropic": MODEL_DEFAULT, "gemini": GEMINI_MODEL_DEFAULT}
MAX_TURNS = 25
MAX_OUTPUT_TOKENS = 1024
# Gemini 3.x Flash bills thinking tokens against this budget, so the Anthropic
# figure would truncate turns before a tool call appeared. Raised for Gemini
# only, and identically for both surfaces - B keeps no turn-budget advantage.
GEMINI_MAX_OUTPUT_TOKENS = 4096
SYSTEM_PROMPT = ("You are a scheduling assistant. Use the tools to actually complete "
                 "the user's request; don't just describe what you would do.")
TRANSCRIPT_DIR = Path(__file__).resolve().parent / "transcripts"

def est_tokens(s):  # display-only estimate for the cover-charge line
    return max(1, round(len(s) / 3.5))

def meter(turn, label, tin, tout, calls, extra=""):
    print(f"  [meter] turn {turn:>2} | {label:<28s} | tokens {tin:>7,} in / {tout:>6,} out | tool calls {calls}{extra}")


# ---------- Anthropic tool definitions -> Gemini function declarations ----------

def to_gemini_declarations(tools):
    """Convert Anthropic-format tool defs to Gemini function declarations.

    Returns (declarations, no_argument_names). Two rules, both pure functions of
    the tool list, so Surface A and Surface B go through identical code:

    1. `input_schema` is passed through verbatim as `parameters_json_schema`.
       Gemini's other field, `parameters`, is an OpenAPI 3.0 subset whose enum
       is string-only, so it rejects Surface B's integer enum on
       duration_minutes. Going that way would mean rewriting one surface's
       schema and not the other's. The JSON Schema field takes both unedited.

    2. A tool with empty `properties` gets no parameters field at all. Gemini
       rejects `{"type":"object","properties":{}}` with "should be non-empty
       for OBJECT type", and an omitted parameters field is the documented way
       to declare a no-argument function. Only Surface A owns such tools, so
       this fires four times for A and zero times for B - same rule, different
       input.
    """
    declarations, no_argument = [], []
    for tool in tools:
        declaration = {"name": tool["name"], "description": tool["description"]}
        schema = tool.get("input_schema") or {}
        if schema.get("properties"):
            declaration["parameters_json_schema"] = schema
        else:
            no_argument.append(tool["name"])
        declarations.append(declaration)
    return declarations, no_argument


def build_gemini_tool(types, tools):
    declarations, no_argument = to_gemini_declarations(tools)
    tool = types.Tool(function_declarations=[types.FunctionDeclaration(**d)
                                            for d in declarations])
    return tool, no_argument


def to_function_response(out):
    """Wrap a surface's return value as a Gemini function response.

    Gemini carries function results as a JSON object; both surfaces return a
    JSON string. Parsing rather than nesting keeps the model looking at the
    same payload the Anthropic path shows it, instead of an escaped string
    whose escape cost would scale with payload size and so inflate Surface A
    more than Surface B. Both surfaces always emit an object, so the fallback
    below never fires in practice; it exists so a malformed payload degrades
    the same way on either surface.
    """
    try:
        parsed = json.loads(out)
    except (TypeError, ValueError):
        return {"result": out}
    return parsed if isinstance(parsed, dict) else {"result": parsed}


# ---------- offline stand-ins ----------

def mock_script(variant):
    """The scripted tool calls both providers' mocks replay: 2 calls, then text."""
    if variant == "a":
        return [("search_contacts", {"query": "priya"}),
                ("get_free_busy", {"contact_id": "priya", "time_min": "2026-08-24T00:00:00Z",
                                   "time_max": "2026-08-29T00:00:00Z"})]
    return [("find_meeting_time", {"attendees": ["Marcus"]}),
            ("schedule_meeting", {"attendees": ["Marcus"], "topic": "Q3 roadmap"})]

class MockClient:
    """Offline stand-in that exercises the full loop: 2 tool calls, then text."""
    def __init__(self, variant):
        self.script = mock_script(variant)
        self.i = 0
    def create(self, **kw):
        if self.i < len(self.script):
            name, args = self.script[self.i]; self.i += 1
            return {"stop_reason": "tool_use", "usage": {"input_tokens": 1200 + 300*self.i,
                    "output_tokens": 60},
                    "content": [{"type": "tool_use", "id": f"mock_{self.i}", "name": name, "input": args}]}
        return {"stop_reason": "end_turn", "usage": {"input_tokens": 1500, "output_tokens": 40},
                "content": [{"type": "text", "text": "(mock) Done - plumbing verified."}]}

class MockGeminiClient:
    """Offline stand-in built from the real SDK response types, so --mock
    exercises the actual function-call parsing and usage-field reads rather
    than a hand-rolled dict. Every number here is a constant, not a
    measurement. The final turn reports a cache hit so the meter's cached
    column is visibly exercised.
    """
    def __init__(self, variant, types):
        self.script = mock_script(variant)
        self.types = types
        self.i = 0
    def _usage(self, prompt, output, thoughts, cached):
        # total reconciles the way the API's does: prompt + candidates +
        # tool_use_prompt + thoughts, with cached a subset of prompt.
        return self.types.GenerateContentResponseUsageMetadata(
            prompt_token_count=prompt, candidates_token_count=output,
            thoughts_token_count=thoughts, cached_content_token_count=cached,
            tool_use_prompt_token_count=0, total_token_count=prompt + output + thoughts)
    def generate_content(self, **kw):
        t = self.types
        if self.i < len(self.script):
            name, args = self.script[self.i]; self.i += 1
            part = t.Part(function_call=t.FunctionCall(id=f"mock_{self.i}", name=name, args=args))
            usage = self._usage(1200 + 300*self.i, 60, 24, 0)
        else:
            part = t.Part(text="(mock) Done - plumbing verified.")
            usage = self._usage(1500, 40, 16, 1100)
        candidate = t.Candidate(content=t.Content(role="model", parts=[part]),
                                finish_reason="STOP")
        return t.GenerateContentResponse(candidates=[candidate], usage_metadata=usage)


# ---------- response normalizers: one plain shape, whatever the provider ----------

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

def gemini_to_plain(resp):
    """Normalize a Gemini response into the same plain shape as to_plain().

    Returns (plain, model_turn). The second value is the model's own Content
    object, kept so it can go back verbatim.

    Token fields per types.GenerateContentResponseUsageMetadata and the
    UsageMetadata proto: total = prompt + candidates + tool_use_prompt +
    thoughts, candidates excludes thinking, and cached_content_token_count is a
    SUBSET of prompt_token_count. So thinking is added to output (it is billed
    as output) and cached is reported but never added - folding it into the
    input total would double-count it, and dropping it would hide a discount
    that only a large repeated catalog can earn.
    """
    usage_meta = getattr(resp, "usage_metadata", None)
    def count(field):
        return int(getattr(usage_meta, field, None) or 0)
    usage = {"input_tokens": count("prompt_token_count") + count("tool_use_prompt_token_count"),
             "output_tokens": count("candidates_token_count") + count("thoughts_token_count"),
             "cached_tokens": count("cached_content_token_count"),
             "thoughts_tokens": count("thoughts_token_count"),
             "reported_total": count("total_token_count")}
    candidates = getattr(resp, "candidates", None) or []
    model_turn = getattr(candidates[0], "content", None) if candidates else None
    finish = getattr(candidates[0], "finish_reason", None) if candidates else None
    blocks = []
    for part in (getattr(model_turn, "parts", None) or []):
        call = getattr(part, "function_call", None)
        if call is not None:
            blocks.append({"type": "tool_use", "id": call.id, "name": call.name,
                           "input": dict(call.args or {})})
        elif getattr(part, "text", None) and not getattr(part, "thought", False):
            blocks.append({"type": "text", "text": part.text})
    stop_reason = "tool_use" if any(b["type"] == "tool_use" for b in blocks) else "end_turn"
    plain = {"stop_reason": stop_reason, "usage": usage, "content": blocks,
             "finish_reason": getattr(finish, "name", None) or (str(finish) if finish else None)}
    return plain, model_turn


# ---------- sessions: same two methods, one per wire format ----------

class AnthropicSession:
    """tool_use blocks out, tool_result blocks back."""
    def __init__(self, surface, model, prompt, variant, mock):
        self.surface, self.model, self.mock = surface, model, mock
        self.no_argument = []
        self.msgs = [{"role": "user", "content": prompt}]
        if mock:
            self.client = MockClient(variant)
        else:
            import anthropic
            self.client = anthropic.Anthropic()

    def send(self):
        if self.mock:
            return to_plain(self.client.create())
        return to_plain(self.client.messages.create(
            model=self.model, max_tokens=MAX_OUTPUT_TOKENS, tools=self.surface.TOOLS,
            system=SYSTEM_PROMPT, messages=self.msgs))

    def record(self, resp, results):
        self.msgs.append({"role": "assistant", "content": resp["content"]})
        self.msgs.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": block["id"], "content": out}
            for block, out in results]})

class GeminiSession:
    """function_call parts out, function_response parts back."""
    def __init__(self, surface, model, prompt, variant, mock):
        try:
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - environment guard
            raise SystemExit("--provider gemini needs the Google GenAI SDK: "
                             "pip install --user google-genai") from exc
        self.types = types
        self.model = model
        self.tool, self.no_argument = build_gemini_tool(types, surface.TOOLS)
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[self.tool],
            max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        self.contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        self.model_turn = None
        if mock:
            self.models = MockGeminiClient(variant, types)
        else:
            from google import genai
            self.models = genai.Client().models

    def send(self):
        resp = self.models.generate_content(model=self.model, contents=self.contents,
                                           config=self.config)
        plain, self.model_turn = gemini_to_plain(resp)
        return plain

    def record(self, resp, results):
        t = self.types
        # The model's Content object goes back as it arrived: Gemini 3 requires
        # thought_signature parts to return inside their original Part, and
        # rebuilding the turn from the normalized dict would strip them.
        if self.model_turn is not None:
            self.contents.append(self.model_turn)
        parts = [t.Part(function_response=t.FunctionResponse(
                     id=block.get("id"), name=block["name"],
                     response=to_function_response(out)))
                 for block, out in results]
        self.contents.append(t.Content(role="user", parts=parts))

SESSIONS = {"anthropic": AnthropicSession, "gemini": GeminiSession}


def run(variant, task_id, model, mock=False, quiet=False, provider="anthropic"):
    surface = surface_a if variant == "a" else surface_b
    task = TASKS[task_id]
    world = World(inject_room_failure=task["failure_switch"])
    catalog = json.dumps(surface.TOOLS, separators=(",", ":"), sort_keys=True)
    if not quiet:
        print(f"\n=== variant {variant.upper()} | task {task_id}: {task['prompt'][:60]}...")
        if task.get("excluded"):
            print(f"  [note] task {task_id} is excluded from the --all grid: {task['excluded']}")
        print(f"  [meter] cover charge: {len(surface.TOOLS)} tools, ~{est_tokens(catalog):,} tokens (est)")
    session = SESSIONS[provider](surface, model, task["prompt"], variant, mock)
    if provider == "gemini" and not quiet:
        wire = json.dumps(to_gemini_declarations(surface.TOOLS)[0],
                          separators=(",", ":"), sort_keys=True)
        print(f"  [meter] gemini wire format: {len(surface.TOOLS)} declarations, "
              f"~{est_tokens(wire):,} tokens (est)")
        print(f"  [note] no-argument tools declared without a parameters field: "
              f"{', '.join(session.no_argument) or 'none'}")
    tin = tout = calls = 0
    cached = thinking = 0
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    tpath = TRANSCRIPT_DIR / f"{variant}_task{task_id}_{int(time.time())}.jsonl"
    t0 = time.time()
    for turn in range(1, MAX_TURNS + 1):
        resp = session.send()
        tin += resp["usage"]["input_tokens"]; tout += resp["usage"]["output_tokens"]
        cached += resp["usage"].get("cached_tokens", 0)
        thinking += resp["usage"].get("thoughts_tokens", 0)
        with tpath.open("a") as fh:
            fh.write(json.dumps(resp) + "\n")
        extra = ""
        if provider == "gemini":
            extra = f" | cached {cached:,} of in | thinking {thinking:,}"
            counted = resp["usage"]["input_tokens"] + resp["usage"]["output_tokens"]
            reported = resp["usage"].get("reported_total")
            if reported and reported != counted:
                print(f"  [warn] turn {turn}: token fields do not reconcile - counted "
                      f"{counted:,}, API reported {reported:,} total")
            if resp.get("finish_reason") not in (None, "STOP"):
                print(f"  [warn] turn {turn}: finish_reason={resp['finish_reason']} - the turn "
                      "was cut short, so this run is not a clean measurement")
        tools_used = [b for b in resp["content"] if b["type"] == "tool_use"]
        if resp["stop_reason"] == "tool_use" and tools_used:
            results = []
            for b in tools_used:
                calls += 1
                out = surface.dispatch(world, b["name"], b["input"])
                if not quiet:
                    meter(turn, b["name"], tin, tout, calls, extra)
                results.append((b, out))
            session.record(resp, results)
            continue
        final = " ".join(b["text"] for b in resp["content"] if b["type"] == "text")
        if not quiet:
            meter(turn, "(final answer)", tin, tout, calls, extra)
            print(f"  agent: {final[:200]}")
        break
    ok = bool(task["check"](world))
    secs = time.time() - t0
    verdict = "SUCCESS" if ok else "FAIL"
    if mock:
        verdict += " (mock: verdict not meaningful)"
    if not quiet:
        print(f"  RESULT: {verdict} | {tin+tout:,} total tokens | {calls} tool calls | {secs:.0f}s")
        if provider == "gemini" and cached:
            print(f"  [meter] {cached:,} of those {tin:,} input tokens were cache hits, billed at a "
                  "discount. Reported, not deducted: a cached catalog is a cheaper catalog, "
                  "not a smaller one.")
    return {"variant": variant, "task": task_id, "ok": ok, "tokens": tin + tout,
            "tin": tin, "tout": tout, "calls": calls, "secs": round(secs),
            "cached": cached, "thinking": thinking}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["a", "b"])
    ap.add_argument("--task", type=int, choices=sorted(TASKS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--provider", choices=sorted(SESSIONS), default="anthropic")
    ap.add_argument("--model", default=None, help="per-provider default: "
                    + ", ".join(f"{p}={m}" for p, m in sorted(MODEL_DEFAULTS.items())))
    args = ap.parse_args()
    model = args.model or MODEL_DEFAULTS[args.provider]
    if args.all:
        rows = [run(v, t, model, mock=args.mock, quiet=False, provider=args.provider)
                for t in GRID for v in ("a", "b")]
        print("\n=== SUMMARY (paste this into the talk repo) ===")
        print(f"provider: {args.provider} | model: {model}"
              + (" | MOCK RUN, numbers are constants" if args.mock else ""))
        print(f"grid: tasks {', '.join(str(t) for t in GRID)} "
              f"({len(GRID)} of {len(TASKS)} defined tasks)")
        for t in EXCLUDED:
            print(f"  excluded task {t}: {TASKS[t]['excluded']} (run it with --task {t})")
        print(f"{'task':>4} | {'A ok':>5} {'A tokens':>9} {'A calls':>7} | {'B ok':>5} {'B tokens':>9} {'B calls':>7}")
        for t in GRID:
            a = next(r for r in rows if r["task"] == t and r["variant"] == "a")
            b = next(r for r in rows if r["task"] == t and r["variant"] == "b")
            print(f"{t:>4} | {str(a['ok']):>5} {a['tokens']:>9,} {a['calls']:>7} |"
                  f" {str(b['ok']):>5} {b['tokens']:>9,} {b['calls']:>7}")
        if args.provider == "gemini":
            for v in ("a", "b"):
                hits = sum(r["cached"] for r in rows if r["variant"] == v)
                think = sum(r["thinking"] for r in rows if r["variant"] == v)
                print(f"surface {v.upper()}: {hits:,} input tokens were cache hits "
                      f"(reported, not deducted); {think:,} output tokens were thinking")
        return
    if not (args.variant and args.task):
        ap.error("either --all, or both --variant and --task")
    run(args.variant, args.task, model, mock=args.mock, provider=args.provider)

if __name__ == "__main__":
    main()
