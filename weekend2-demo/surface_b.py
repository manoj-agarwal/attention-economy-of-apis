#!/usr/bin/env python3
"""Surface B: the task-oriented surface. Six tools named after outcomes.

The choreography (timezone math, conflict search, room booking, invites,
retries) lives inside the tools, where it is deterministic and costs no tokens.
Responses are lean. Errors are actionable. No secret powers: everything here
calls the same world primitives Surface A uses.
"""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from calendar_world import PEOPLE, ROOMS, WORK_START, WORK_END, RoomBusyError, TransientRoomError


def _t(name, desc, props, req):
    return {"name": name, "description": desc,
            "input_schema": {"type": "object", "properties": props, "required": req}}

_PEOPLE_DESC = {"type": "array", "items": {"type": "string"},
                "description": "Names or emails, e.g. ['Priya','Marcus']. 'you' is implicit."}

TOOLS = [
    _t("get_schedule_summary",
       "Use when the user asks what is on their (or a colleague's) calendar. Returns a "
       "short human-readable summary in the person's local timezone.",
       {"person": {"type": "string", "description": "Defaults to 'you'."},
        "day": {"type": "string", "description": "e.g. 'tomorrow', 'friday', or YYYY-MM-DD."}},
       ["day"]),
    _t("find_meeting_time",
       "Use to find candidate slots that work for several people. Handles timezones and "
       "working hours internally. Returns up to 3 candidate start times with rationale.",
       {"attendees": _PEOPLE_DESC,
        "duration_minutes": {"type": "integer", "enum": [15, 30, 45, 60], "description": "Default 30."},
        "within_days": {"type": "integer", "description": "Search window from today. Default 10."}},
       ["attendees"]),
    _t("schedule_meeting",
       "Use when the user wants a meeting to exist. Finds a mutually free slot (or uses "
       "'start' if given), checks conflicts, books a room if asked, creates the event, and "
       "sends invitations - one step. Retries transient infrastructure errors automatically.",
       {"attendees": _PEOPLE_DESC,
        "topic": {"type": "string", "description": "Used as the event title."},
        "duration_minutes": {"type": "integer", "enum": [15, 30, 45, 60], "description": "Default 30."},
        "start": {"type": "string", "description": "Optional RFC3339 start; omit to auto-pick."},
        "room": {"type": "string", "description": "Optional room name, e.g. 'Aurora'."},
        "within_days": {"type": "integer", "description": "Search window if start omitted. Default 10."}},
       ["attendees", "topic"]),
    _t("reschedule_meeting",
       "Use to move an existing meeting. Finds the event by title/participant, picks the "
       "next slot free for all attendees (or uses 'start'), moves it, notifies attendees.",
       {"match": {"type": "string", "description": "Words from the meeting title or an attendee name."},
        "start": {"type": "string", "description": "Optional RFC3339 start; omit to auto-pick later this week."},
        "notify_message": {"type": "string", "description": "Optional note to attendees."}},
       ["match"]),
    _t("cancel_meetings",
       "Use to cancel one or many meetings. Cancels everything matching the day and/or "
       "title filter on the user's calendar and notifies all attendees.",
       {"day": {"type": "string", "description": "e.g. 'friday' or YYYY-MM-DD."},
        "match": {"type": "string", "description": "Optional title filter."}},
       ["day"]),
    _t("block_focus_time",
       "Use to reserve personal focus time on the user's calendar around existing meetings.",
       {"hours": {"type": "integer", "description": "Total hours to block. Default 2."},
        "day": {"type": "string", "description": "e.g. 'thursday'."}},
       ["day"]),
]

# ---------- helpers (choreography lives here, off the model's desk) ----------

def _pid(token):
    t = token.strip().lower()
    for pid, p in PEOPLE.items():
        if t in (pid, p["name"].lower(), p["email"].lower()):
            return pid
    raise KeyError(token)

def _day(world, word):
    w = (word or "").strip().lower()
    names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if w == "tomorrow":
        return world.t0 + timedelta(days=1)
    if w in names:
        d = world.t0
        for _ in range(14):
            if d.strftime("%A").lower() == w:
                return d
            d += timedelta(days=1)
    return datetime.fromisoformat(w).replace(tzinfo=timezone.utc)

def _all_free(world, pids, start, end):
    return all(not world.busy(p, start, end) for p in pids)

def _candidates(world, pids, minutes, within_days, limit=3, after=None):
    out = []
    for d in range(1, within_days + 1):
        day = world.t0 + timedelta(days=d)
        if day.weekday() >= 5:
            continue
        for h in range(WORK_START, WORK_END):          # user-local working hours
            for m in (0, 30):
                local = day.astimezone(ZoneInfo(PEOPLE["you"]["tz"])).replace(hour=h, minute=m)
                start = local.astimezone(timezone.utc)
                if after is not None and start <= after:
                    continue
                end = start + timedelta(minutes=minutes)
                # everyone's local working hours too
                if not all(WORK_START <= start.astimezone(ZoneInfo(PEOPLE[p]["tz"])).hour < WORK_END
                           for p in pids):
                    continue
                if _all_free(world, pids, start, end):
                    out.append(start)
                    if len(out) >= limit:
                        return out
    return out

def _fmt(start, pids):
    parts = [f"{start.astimezone(ZoneInfo(PEOPLE[p]['tz'])).strftime('%a %H:%M')} for {PEOPLE[p]['name']}"
             for p in pids]
    return f"{start.strftime('%a %Y-%m-%d %H:%M UTC')} ({'; '.join(parts)})"

# ---------- dispatch ----------

def dispatch(world, name, args):
    try:
        if name == "get_schedule_summary":
            pid = _pid(args.get("person", "you"))
            day = _day(world, args["day"])
            evs = sorted(world.busy(pid, day, day + timedelta(days=1)), key=lambda e: e["start"])
            tz = ZoneInfo(PEOPLE[pid]["tz"])
            lines = [f"- {e['start'].astimezone(tz).strftime('%H:%M')} {e['title']}" for e in evs]
            return json.dumps({"summary": f"{len(evs)} meetings on {day.strftime('%A')}",
                               "detail": lines})
        if name == "find_meeting_time":
            pids = ["you"] + [_pid(a) for a in args["attendees"] if _pid(a) != "you"]
            mins = args.get("duration_minutes", 30)
            cands = _candidates(world, pids, mins, args.get("within_days", 10))
            if not cands:
                return json.dumps({"candidates": [], "note": "No common slot in window; "
                                   "try fewer attendees, a shorter duration, or a wider window."})
            return json.dumps({"candidates": [_fmt(c, pids) for c in cands],
                               "starts": [c.isoformat() for c in cands]})
        if name == "schedule_meeting":
            pids = ["you"] + [_pid(a) for a in args["attendees"] if _pid(a) != "you"]
            mins = args.get("duration_minutes", 30)
            if args.get("start"):
                start = datetime.fromisoformat(args["start"].replace("Z", "+00:00"))
                if not _all_free(world, pids, start, start + timedelta(minutes=mins)):
                    alts = _candidates(world, pids, mins, args.get("within_days", 10))
                    hint = f" Nearest slot free for all: {alts[0].isoformat()}." if alts else ""
                    return json.dumps({"error": "conflict",
                                       "message": f"That time conflicts for at least one attendee.{hint} "
                                                  "Retry with that start, or omit start to auto-pick."})
            else:
                cands = _candidates(world, pids, mins, args.get("within_days", 10))
                if not cands:
                    return json.dumps({"error": "no_slot", "message": "No common slot in the window. "
                                       "Widen within_days or shorten the meeting."})
                start = cands[0]
            end = start + timedelta(minutes=mins)
            room_note = ""
            if args.get("room"):
                rid = args["room"].strip().lower().replace("room ", "")
                for attempt in (1, 2):
                    try:
                        world.book_room(rid, start, end); room_note = f" {ROOMS[rid]} booked."
                        break
                    except TransientRoomError:
                        room_note = f" {ROOMS[rid]} booked after one automatic retry (transient 503)."
                        continue
                    except RoomBusyError:
                        return json.dumps({"error": "room_busy",
                                           "message": f"{ROOMS[rid]} is taken then. Pick another room "
                                                      "or omit start to auto-pick a slot."})
            eid = world.create_event(args["topic"], pids, start, end)
            for p in pids:
                if p != "you":
                    world.send_invite(eid, p)
            return json.dumps({"scheduled": _fmt(start, pids), "event_id": eid,
                               "invites_sent": len(pids) - 1, "note": room_note.strip()})
        if name == "reschedule_meeting":
            m = args["match"].lower()
            hits = [e for e in world.events.values() if e["status"] == "confirmed"
                    and "you" in e["attendees"]
                    and (m in e["title"].lower()
                         or any(m in PEOPLE[a]["name"].lower() for a in e["attendees"]))]
            if not hits:
                return json.dumps({"error": "not_found",
                                   "message": f"No confirmed meeting matches '{args['match']}'."})
            e = sorted(hits, key=lambda x: x["start"])[0]
            mins = int((e["end"] - e["start"]).total_seconds() // 60)
            if args.get("start"):
                start = datetime.fromisoformat(args["start"].replace("Z", "+00:00"))
            else:
                cands = _candidates(world, e["attendees"], mins, 5, after=e["start"])
                if not cands:
                    return json.dumps({"error": "no_slot", "message": "No later common slot this week."})
                start = cands[0]
            world.move_event(e["id"], start, start + timedelta(minutes=mins))
            for p in e["attendees"]:
                if p != "you":
                    world.notify(p, args.get("notify_message", f"'{e['title']}' moved to {start.isoformat()}"))
            return json.dumps({"rescheduled": e["title"], "new_time": _fmt(start, e["attendees"])})
        if name == "cancel_meetings":
            day = _day(world, args["day"])
            m = args.get("match", "").lower()
            evs = [e for e in world.busy("you", day, day + timedelta(days=1))
                   if not e["seeded"] or True]  # user's meetings that day
            evs = [e for e in evs if m in e["title"].lower()] if m else evs
            for e in evs:
                world.cancel_event(e["id"])
                for p in e["attendees"]:
                    if p != "you":
                        world.notify(p, f"'{e['title']}' on {day.strftime('%A')} is cancelled.")
            return json.dumps({"cancelled": len(evs), "notified": sum(len(e['attendees']) - 1 for e in evs)})
        if name == "block_focus_time":
            day = _day(world, args["day"])
            hours = args.get("hours", 2)
            cands = _candidates(world, ["you"], hours * 60, 14)
            same_day = [c for c in cands if c.date() == day.date()] or cands[:1]
            if not same_day:
                return json.dumps({"error": "no_slot", "message": "No free block that day."})
            s = same_day[0]
            world.create_event("Focus time", ["you"], s, s + timedelta(hours=hours))
            return json.dumps({"blocked": _fmt(s, ["you"])})
        return json.dumps({"error": "unknown_tool", "message": f"No tool named {name}."})
    except KeyError as exc:
        return json.dumps({"error": "unknown_person",
                           "message": f"I don't know {exc}. Known people: "
                                      f"{', '.join(p['name'] for p in PEOPLE.values())}."})
