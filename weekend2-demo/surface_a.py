#!/usr/bin/env python3
"""Surface A: the 1:1 endpoint wrapper. Competent, honest, terse. 28 tools.

Fairness rules embodied here: schemas are accurate; descriptions are truthful
(in the pasted-from-API-reference style real wrappers use); payloads return the
full object the way real REST APIs do; errors relay bare status codes, because
that is what thin wrappers actually relay.
"""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from calendar_world import PEOPLE, ROOMS, RoomBusyError, TransientRoomError

def _iso(dt): return dt.astimezone(timezone.utc).isoformat()

def _event_payload(e):
    # Real APIs return everything. So do we. (Payload tax, honestly earned.)
    return {"kind": "calendar#event", "id": e["id"], "etag": f'"{hash(e["id"]) & 0xffff}"',
            "status": e["status"], "summary": e["title"],
            "creator": {"id": e["organizer"], "email": PEOPLE[e["organizer"]]["email"]},
            "organizer": {"id": e["organizer"], "self": e["organizer"] == "you"},
            "start": {"dateTime": _iso(e["start"]), "timeZone": "UTC"},
            "end": {"dateTime": _iso(e["end"]), "timeZone": "UTC"},
            "attendees": [{"id": a, "email": PEOPLE[a]["email"], "responseStatus": "needsAction"}
                          for a in e["attendees"]],
            "room": e["room"], "iCalUID": f"{e['id']}@acme.dev", "sequence": 0,
            "reminders": {"useDefault": True}, "visibility": "default"}

def _t(name, desc, props, req):
    return {"name": name, "description": desc,
            "input_schema": {"type": "object", "properties": props, "required": req}}

_ID = {"type": "string"}
_TIME = {"type": "string", "description": "RFC3339 timestamp, e.g. 2026-08-24T17:00:00Z"}

TOOLS = [
    _t("list_contacts", "Returns a paginated list of Contact resources.",
       {"page_token": _ID, "max_results": {"type": "integer"}}, []),
    _t("search_contacts", "Returns Contact resources matching the query string.",
       {"query": {"type": "string"}}, ["query"]),
    _t("get_contact", "Returns the Contact resource for the specified contact_id.",
       {"contact_id": _ID}, ["contact_id"]),
    _t("get_contact_timezone", "Returns the IANA timezone for the specified contact_id.",
       {"contact_id": _ID}, ["contact_id"]),
    _t("get_working_hours", "Returns working-hour configuration for the contact_id.",
       {"contact_id": _ID}, ["contact_id"]),
    _t("list_calendars", "Returns the CalendarList collection for the authenticated principal.",
       {"page_token": _ID}, []),
    _t("get_calendar", "Returns the Calendar resource for the specified calendar_id.",
       {"calendar_id": _ID}, ["calendar_id"]),
    _t("list_events", "Returns Event resources on the specified calendar between time_min and time_max.",
       {"calendar_id": _ID, "time_min": _TIME, "time_max": _TIME, "page_token": _ID},
       ["calendar_id", "time_min", "time_max"]),
    _t("get_event", "Returns the Event resource for the specified event_id.",
       {"event_id": _ID}, ["event_id"]),
    _t("create_event", "Creates an Event resource on the specified calendar. Returns the created Event.",
       {"calendar_id": _ID, "summary": {"type": "string"}, "start": _TIME, "end": _TIME,
        "attendee_ids": {"type": "array", "items": {"type": "string"}}},
       ["calendar_id", "summary", "start", "end"]),
    _t("update_event", "Updates start/end/summary fields of the specified Event resource.",
       {"event_id": _ID, "start": _TIME, "end": _TIME, "summary": {"type": "string"}}, ["event_id"]),
    _t("delete_event", "Sets the specified Event resource status to cancelled.",
       {"event_id": _ID}, ["event_id"]),
    _t("get_event_attendees", "Returns the attendee sub-collection of the specified Event.",
       {"event_id": _ID}, ["event_id"]),
    _t("add_event_attendee", "Adds a contact_id to the attendee sub-collection of the Event.",
       {"event_id": _ID, "contact_id": _ID}, ["event_id", "contact_id"]),
    _t("get_free_busy", "Returns busy intervals for the contact_id between time_min and time_max.",
       {"contact_id": _ID, "time_min": _TIME, "time_max": _TIME},
       ["contact_id", "time_min", "time_max"]),
    _t("get_availability", "Alias of get_free_busy maintained for backward compatibility.",
       {"contact_id": _ID, "time_min": _TIME, "time_max": _TIME},
       ["contact_id", "time_min", "time_max"]),
    _t("list_rooms", "Returns the Room resource collection.", {}, []),
    _t("get_room", "Returns the Room resource for the specified room_id.", {"room_id": _ID}, ["room_id"]),
    _t("get_room_availability", "Returns busy intervals for the room_id between time_min and time_max.",
       {"room_id": _ID, "time_min": _TIME, "time_max": _TIME}, ["room_id", "time_min", "time_max"]),
    _t("book_room", "Creates a RoomBooking resource for the room_id.",
       {"room_id": _ID, "start": _TIME, "end": _TIME}, ["room_id", "start", "end"]),
    _t("cancel_room_booking", "Deletes the specified RoomBooking resource.",
       {"booking_id": _ID}, ["booking_id"]),
    _t("send_invite", "Sends an invitation for the event_id to the contact_id.",
       {"event_id": _ID, "contact_id": _ID}, ["event_id", "contact_id"]),
    _t("get_invite_status", "Returns invitation delivery status for the event_id.",
       {"event_id": _ID}, ["event_id"]),
    _t("send_notification", "Sends a notification message to the contact_id.",
       {"contact_id": _ID, "message": {"type": "string"}}, ["contact_id", "message"]),
    _t("get_current_time", "Returns the current server time as an RFC3339 timestamp.", {}, []),
    _t("list_holidays", "Returns Holiday resources for the specified year.",
       {"year": {"type": "integer"}}, ["year"]),
    _t("get_notification_settings", "Returns NotificationSettings for the authenticated principal.", {}, []),
    _t("get_user_preferences", "Returns UserPreferences for the authenticated principal.", {}, []),
]


def dispatch(world, name, args):
    """Execute one endpoint-shaped call. Returns a JSON string, like a real wrapper."""
    try:
        world.api_calls += 1
        if name in ("list_contacts",):
            return json.dumps({"items": [{"id": p, **PEOPLE[p]} for p in PEOPLE], "nextPageToken": None})
        if name == "search_contacts":
            q = args["query"].lower()
            hits = [{"id": p, **PEOPLE[p]} for p in PEOPLE
                    if q in p or q in PEOPLE[p]["name"].lower() or q in PEOPLE[p]["email"]]
            return json.dumps({"items": hits})
        if name == "get_contact":
            p = args["contact_id"]; return json.dumps({"id": p, **PEOPLE[p]})
        if name == "get_contact_timezone":
            return json.dumps({"contact_id": args["contact_id"], "timeZone": PEOPLE[args["contact_id"]]["tz"]})
        if name == "get_working_hours":
            return json.dumps({"contact_id": args["contact_id"], "start": "09:00", "end": "17:00",
                               "days": ["MON", "TUE", "WED", "THU", "FRI"]})
        if name == "list_calendars":
            return json.dumps({"items": [{"id": f"cal_{p}", "owner": p, "primary": True} for p in PEOPLE]})
        if name == "get_calendar":
            return json.dumps({"id": args["calendar_id"], "timeZone": "UTC", "accessRole": "owner"})
        if name in ("list_events",):
            pid = args["calendar_id"].removeprefix("cal_")
            lo, hi = _parse(args["time_min"]), _parse(args["time_max"])
            evs = world.busy(pid, lo, hi)
            return json.dumps({"items": [_event_payload(e) for e in evs], "nextPageToken": None})
        if name == "get_event":
            return json.dumps(_event_payload(world.events[args["event_id"]]))
        if name == "create_event":
            eid = world.create_event(args["summary"], args.get("attendee_ids", ["you"]),
                                     _parse(args["start"]), _parse(args["end"]))
            return json.dumps(_event_payload(world.events[eid]))
        if name == "update_event":
            e = world.events[args["event_id"]]
            world.move_event(e["id"], _parse(args.get("start", _iso(e["start"]))),
                             _parse(args.get("end", _iso(e["end"]))))
            if "summary" in args: e["title"] = args["summary"]
            return json.dumps(_event_payload(e))
        if name == "delete_event":
            world.cancel_event(args["event_id"]); return json.dumps({"status": "cancelled"})
        if name == "get_event_attendees":
            e = world.events[args["event_id"]]
            return json.dumps({"items": [{"id": a, "email": PEOPLE[a]["email"]} for a in e["attendees"]]})
        if name == "add_event_attendee":
            e = world.events[args["event_id"]]
            if args["contact_id"] not in e["attendees"]: e["attendees"].append(args["contact_id"])
            world.api_calls += 0
            return json.dumps(_event_payload(e))
        if name in ("get_free_busy", "get_availability"):
            lo, hi = _parse(args["time_min"]), _parse(args["time_max"])
            busy = world.busy(args["contact_id"], lo, hi)
            return json.dumps({"contact_id": args["contact_id"],
                               "busy": [{"start": _iso(b["start"]), "end": _iso(b["end"])} for b in busy]})
        if name == "list_rooms":
            return json.dumps({"items": [{"id": r, "name": n, "capacity": 8} for r, n in ROOMS.items()]})
        if name == "get_room":
            return json.dumps({"id": args["room_id"], "name": ROOMS[args["room_id"]], "capacity": 8})
        if name == "get_room_availability":
            lo, hi = _parse(args["time_min"]), _parse(args["time_max"])
            busy = [b for b in world.room_bookings.values()
                    if b["room"] == args["room_id"] and b["start"] < hi and b["end"] > lo]
            return json.dumps({"room_id": args["room_id"],
                               "busy": [{"start": _iso(b["start"]), "end": _iso(b["end"])} for b in busy]})
        if name == "book_room":
            bid = world.book_room(args["room_id"], _parse(args["start"]), _parse(args["end"]))
            return json.dumps({"id": bid, "room_id": args["room_id"], "status": "confirmed"})
        if name == "cancel_room_booking":
            world.room_bookings.pop(args["booking_id"], None); return json.dumps({"status": "deleted"})
        if name == "send_invite":
            world.send_invite(args["event_id"], args["contact_id"]); return json.dumps({"status": "sent"})
        if name == "get_invite_status":
            return json.dumps({"event_id": args["event_id"], "invites": world.invites.get(args["event_id"], {})})
        if name == "send_notification":
            world.notify(args["contact_id"], args["message"]); return json.dumps({"status": "sent"})
        if name == "get_current_time":
            return json.dumps({"time": _iso(world.t0)})
        if name == "list_holidays":
            return json.dumps({"items": []})
        if name == "get_notification_settings":
            return json.dumps({"email": True, "push": False, "digest": "daily"})
        if name == "get_user_preferences":
            return json.dumps({"locale": "en-US", "weekStart": "MON", "defaultMeetingLength": 30})
        return json.dumps({"error": "404 Not Found"})
    except TransientRoomError:
        return json.dumps({"error": "503 Service Unavailable"})
    except RoomBusyError:
        return json.dumps({"error": "409 Conflict"})
    except KeyError:
        return json.dumps({"error": "400 Bad Request"})
    except Exception:
        return json.dumps({"error": "500 Internal Server Error"})


def _parse(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
