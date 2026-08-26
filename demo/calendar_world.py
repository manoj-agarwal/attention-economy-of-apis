#!/usr/bin/env python3
"""A small, deterministic calendar world. Both surfaces run on top of this.

Times are timezone-aware datetimes stored in UTC. People live in different
timezones on purpose: timezone choreography is part of the demo's honest pain.
"""
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SEED = 1776  # the median made me do it

PEOPLE = {
    "you":    {"name": "You",    "email": "you@acme.dev",    "tz": "America/Los_Angeles"},
    "priya":  {"name": "Priya",  "email": "priya@acme.dev",  "tz": "Europe/London"},
    "marcus": {"name": "Marcus", "email": "marcus@acme.dev", "tz": "America/New_York"},
    "elena":  {"name": "Elena",  "email": "elena@acme.dev",  "tz": "Asia/Kolkata"},
    "sam":    {"name": "Sam",    "email": "sam@acme.dev",    "tz": "America/Los_Angeles"},
}
ROOMS = {"aurora": "Room Aurora", "basalt": "Room Basalt", "cirrus": "Room Cirrus"}
WORK_START, WORK_END = 9, 17  # local hours


def _monday_anchor():
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return now + timedelta(days=(7 - now.weekday()) % 7 or 7)  # next Monday


class World:
    def __init__(self, inject_room_failure=False):
        rng = random.Random(SEED)
        self.t0 = _monday_anchor()
        self.events = {}      # id -> event dict
        self.room_bookings = {}   # id -> booking dict
        self.invites = {}     # event_id -> {person_id: status}
        self.notifications = []   # (person_id, text)
        self._next = 100
        self.inject_room_failure = inject_room_failure
        self._room_failures_left = 1 if inject_room_failure else 0
        self.api_calls = 0    # world-level odometer, both surfaces tick it

        # Seed busy blocks: 10 weekdays, 1-3 meetings/person/day in local work hours.
        for pid, p in PEOPLE.items():
            tz = ZoneInfo(p["tz"])
            for d in range(14):
                day = self.t0 + timedelta(days=d)
                if day.weekday() >= 5:
                    continue
                for _ in range(rng.randint(1, 3)):
                    h = rng.randint(WORK_START, WORK_END - 2)
                    local = day.astimezone(tz).replace(hour=h, minute=rng.choice([0, 30]))
                    start = local.astimezone(timezone.utc)
                    self._add_event(f"{p['name']}'s meeting", [pid], start,
                                    start + timedelta(minutes=rng.choice([30, 60])),
                                    organizer=pid, seeded=True)
        # A standing 1:1 with Sam on Tuesday for the reschedule task.
        tue = (self.t0 + timedelta(days=1)).replace(hour=18, minute=0)  # 10:00 PT
        self.sam_11 = self._add_event("1:1 You / Sam", ["you", "sam"], tue,
                                      tue + timedelta(minutes=30), organizer="you",
                                      seeded=True)

    # ---- primitive operations (both surfaces call these) ----
    def _add_event(self, title, attendees, start, end, organizer, seeded=False):
        eid = f"evt_{self._next}"; self._next += 1
        self.events[eid] = {"id": eid, "title": title, "attendees": list(attendees),
                            "start": start, "end": end, "organizer": organizer,
                            "status": "confirmed", "seeded": seeded, "room": None}
        return eid

    def busy(self, pid, start, end):
        return [e for e in self.events.values()
                if pid in e["attendees"] and e["status"] == "confirmed"
                and e["start"] < end and e["end"] > start]

    def create_event(self, title, attendees, start, end, organizer="you"):
        self.api_calls += 1
        return self._add_event(title, attendees, start, end, organizer)

    def cancel_event(self, eid):
        self.api_calls += 1
        self.events[eid]["status"] = "cancelled"

    def move_event(self, eid, start, end):
        self.api_calls += 1
        self.events[eid]["start"], self.events[eid]["end"] = start, end

    def book_room(self, room_id, start, end):
        self.api_calls += 1
        if self._room_failures_left > 0:
            self._room_failures_left -= 1
            raise TransientRoomError("room service temporarily unavailable")
        for b in self.room_bookings.values():
            if b["room"] == room_id and b["start"] < end and b["end"] > start:
                raise RoomBusyError(room_id)
        bid = f"bkg_{self._next}"; self._next += 1
        self.room_bookings[bid] = {"id": bid, "room": room_id, "start": start, "end": end}
        return bid

    def send_invite(self, eid, pid):
        self.api_calls += 1
        self.invites.setdefault(eid, {})[pid] = "sent"

    def notify(self, pid, text):
        self.api_calls += 1
        self.notifications.append((pid, text))


class TransientRoomError(Exception):
    pass


class RoomBusyError(Exception):
    pass
