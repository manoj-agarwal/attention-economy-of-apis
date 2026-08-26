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
        # Excluded from the published grid, human ruling 2026-08-14: the check is
        # always true, so the row reports SUCCESS whatever either surface does.
        # Still runnable on demand with --task 1.
        "excluded": "always-true check; the row reports SUCCESS regardless of behaviour",
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
        # Excluded from the published grid, human ruling 2026-08-14: unpassable by
        # either surface. Still runnable on demand with --task 6.
        "excluded": "unpassable by both surfaces: 'you' has no Friday meetings under the "
                    "day-shifted seeding, and the seeding fix was declined",
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
    9: {"prompt": "Set up my weekly 1:1s for next week: 30 minutes with Marcus and 30 "
                  "minutes with Sam, and send them both invites.",
        "failure_switch": False,
        "check": lambda w: all(
            any(set(e["attendees"]) == {"you", who} and _minutes(e) == 30 and _humane(e)
                and w.invites.get(e["id"], {}).get(who) == "sent"
                for e in _new_events(w))
            for who in ("marcus", "sam")),
        "note": "Repetition. The grid had no task requiring the same choreography twice, so "
                "nothing measured whether Surface A's per-primitive cost compounds or "
                "amortises. Two independent two-person meetings, no room, no notification.\n"
                "PREDICTION (written 2026-08-15, before the first run): A repeats "
                "find/create/attendee/invite per meeting and lands near twice task 2's 10 "
                "calls, so 16-22; B calls schedule_meeting twice, so 2. Widest absolute call "
                "gap in the grid.\n"
                "FALSIFIED IF: A finishes in ~10 calls by reusing one free/busy sweep across "
                "both meetings. That would mean the cost amortises and this task says nothing "
                "task 2 didn't."},
    10: {"prompt": "Get the three of us together for a 60-minute planning session in Room "
                   "Basalt next week, send everyone invites, and block me two hours of prep "
                   "time.",
         "failure_switch": False,
         "check": lambda w: (
             any(set(e["attendees"]) == {"you", "marcus", "sam"}
                 and _minutes(e) == 60
                 and _humane(e)
                 and any(b["room"] == "basalt" and b["start"] == e["start"]
                         for b in w.room_bookings.values())
                 and all(w.invites.get(e["id"], {}).get(p) == "sent" for p in ("marcus", "sam"))
                 for e in _new_events(w))
             and any(set(e["attendees"]) == {"you"} and _minutes(e) == 120 and _humane(e)
                     for e in _new_events(w))),
         # Excluded from the published grid, human ruling 2026-08-15, after one run
         # of each surface. Kept runnable with --task 10, and the prediction below
         # is left exactly as registered so the miss stays auditable.
         "excluded": "both surfaces failed without writing anything: B spent every call on "
                     "get_schedule_summary starting from an unparseable day='next week', A "
                     "spent every call on reads and looked at the week before the world's "
                     "start date. Verified passable by script, but not findable by a model - "
                     "a defect in the task, not a property of either surface",
         "note": "Additivity. Task 3 (three people + room + invites) and task 7 (meeting + "
                 "focus block) each test one shape; nothing tested whether A's cost simply "
                 "adds when a request carries both. Room Basalt, not Aurora, so it shares no "
                 "state with task 3.\n"
                 "PREDICTION (written 2026-08-15, before the first run): A pays task 3's "
                 "sequence plus a focus-time create, so 18-24 calls; B needs exactly two "
                 "tools, schedule_meeting and block_focus_time, so 2 - the same count as task "
                 "9 despite far more work per call.\n"
                 "FALSIFIED IF: B needs more than 2 calls, or A comes in at or below its task "
                 "3 count of 20, which would mean the second sub-goal was effectively free.\n"
                 "OUTCOME 2026-08-15: BOTH falsifiers fired - B took 6 calls, A took 7 - and "
                 "both surfaces failed without creating anything. Prediction wrong; task "
                 "excluded rather than tuned."},
    8: {"prompt": "Cancel my 1:1 with Sam and let him know.",
        "failure_switch": False,
        "check": lambda w: (w.events[w.sam_11]["status"] == "cancelled"
                            and any(p == "sam" for p, _ in w.notifications)),
        "note": "Suits Surface A: one known event, one delete, one notification. B must first "
                "locate the day before it can cancel, so the gap here should be narrow."},
}

# The published grid. Excluded tasks stay defined above and stay runnable via
# --task N; they are dropped from --all rather than deleted, so the reason a row
# is missing travels with the table instead of living only in someone's memory.
GRID = [tid for tid in sorted(TASKS) if not TASKS[tid].get("excluded")]
EXCLUDED = [tid for tid in sorted(TASKS) if TASKS[tid].get("excluded")]
