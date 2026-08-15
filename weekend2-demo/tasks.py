#!/usr/bin/env python3
"""Eight tasks. Each has the user's opening message and a check(world) that
inspects final world state. Success is defined by outcomes, not transcripts.

Casts: scheduling tasks draw only from you/Marcus/Sam (LA, NY, LA). Priya
(London) and Elena (Kolkata) have no working-hour overlap with LA under the
9-17 policy both surfaces enforce, so a meeting with them is unschedulable by
construction rather than by skill - see BUILDLOG 2026-08-14.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from calendar_world import PEOPLE, WORK_START, WORK_END


def _new_events(world):
    return [e for e in world.events.values() if not e["seeded"] and e["status"] == "confirmed"]


def _humane(e):
    """True when every attendee sees the meeting inside their own working day.

    Without this, a surface can 'succeed' by booking a slot that is 05:30 for
    somebody. Scoring has to hold both surfaces to the same standard.
    """
    for pid in e["attendees"]:
        tz = ZoneInfo(PEOPLE[pid]["tz"])
        start, end = e["start"].astimezone(tz), e["end"].astimezone(tz)
        if start.date() != end.date():
            return False
        if start.hour * 60 + start.minute < WORK_START * 60:
            return False
        if end.hour * 60 + end.minute > WORK_END * 60:
            return False
    return True


def _minutes(e):
    return int((e["end"] - e["start"]).total_seconds() // 60)


TASKS = {
    1: {"prompt": "What's on my calendar tomorrow?",
        "failure_switch": False,
        "check": lambda w: True,  # informational; judge by transcript, both surfaces should breeze
        "note": "Fairness task: A should succeed too. Shows B is not magic."},
    2: {"prompt": "Schedule 30 minutes with Marcus next week to talk through the Q3 roadmap.",
        "failure_switch": False,
        "check": lambda w: any(set(e["attendees"]) == {"you", "marcus"} and "q3" in e["title"].lower()
                               and _humane(e)
                               and not w.busy("marcus", e["start"], e["end"])[1:]
                               for e in _new_events(w)),
        "note": "Two-person, cross-timezone (LA/NY)."},
    3: {"prompt": ("Find a time in the next two weeks for me, Marcus, and Sam to do a "
                   "60-minute launch review. Book Room Aurora for it and send everyone invites."),
        "failure_switch": False,
        "check": lambda w: any(
            set(e["attendees"]) == {"you", "marcus", "sam"}
            and _minutes(e) == 60
            and _humane(e)
            and any(b["room"] == "aurora" and b["start"] == e["start"] for b in w.room_bookings.values())
            and all(w.invites.get(e["id"], {}).get(p) == "sent" for p in ("marcus", "sam"))
            for e in _new_events(w)),
        "note": "THE HERO TASK. Three people, two timezones, a room, invites."},
    4: {"prompt": "Move my 1:1 with Sam to later this week and let him know why.",
        "failure_switch": False,
        "check": lambda w: (w.events[w.sam_11]["start"] > w.t0 + timedelta(days=1, hours=19)
                            and _humane(w.events[w.sam_11])
                            and any(p == "sam" for p, _ in w.notifications)),
        "note": "Find-then-modify plus a courtesy notification."},
    5: {"prompt": ("Find a time in the next two weeks for me, Marcus, and Sam to do a "
                   "60-minute launch review. Book Room Aurora for it and send everyone invites."),
        "failure_switch": True,
        "check": lambda w: TASKS[3]["check"](w),
        "note": "Same as task 3 with one injected transient 503 on room booking. The error-tax beat."},
    6: {"prompt": "Clear my Friday: cancel my meetings that day and make sure people are told.",
        "failure_switch": False,
        "check": lambda w: all(
            e["status"] == "cancelled"
            for e in w.events.values()
            if "you" in e["attendees"] and e["start"].strftime("%A") == "Friday"
            and e["start"] < w.t0 + timedelta(days=7)) and len(w.notifications) > 0,
        "note": "Bulk operation with side duty (notifications). KNOWN BROKEN: the world's "
                "day-shifted seeding leaves 'you' with no Friday meetings, so the cancellation "
                "clause is vacuous and only the notification clause bites. Left as-is by "
                "human decision on 2026-08-14."},
    7: {"prompt": ("Set up a 45-minute design sync with Marcus and Sam next week, and block me "
                   "two hours of focus time to prepare for it."),
        "failure_switch": False,
        "check": lambda w: (
            any(set(e["attendees"]) == {"you", "marcus", "sam"} and _minutes(e) == 45
                and _humane(e)
                and all(w.invites.get(e["id"], {}).get(p) == "sent" for p in ("marcus", "sam"))
                for e in _new_events(w))
            and any(set(e["attendees"]) == {"you"} and _minutes(e) == 120 and _humane(e)
                    for e in _new_events(w))),
        "note": "Two outcomes in one request: Surface B needs schedule_meeting AND "
                "block_focus_time, so this task breaks the one-tool-per-task mapping."},
    8: {"prompt": "Cancel my 1:1 with Sam and let him know.",
        "failure_switch": False,
        "check": lambda w: (w.events[w.sam_11]["status"] == "cancelled"
                            and any(p == "sam" for p, _ in w.notifications)),
        "note": "Suits Surface A: one known event, one delete, one notification. B must first "
                "locate the day before it can cancel, so the gap here should be narrow."},
}
