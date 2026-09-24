"""Calendar windows, normalization and week layout for the Mira Home MCP.

All day boundaries are local midnights in the operator-configured IANA zone,
built with ``datetime.combine(day, time.min, tzinfo=zone)``. Never derive a
day's end as ``start + timedelta(hours=24)``: DST days are 23 or 25 hours long.

Aware datetimes that share one ``ZoneInfo`` compare and subtract as wall-clock
values in Python, so every comparison, sort and overlap check here converts to
UTC first. Output timestamps are rendered back in the configured zone.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from .ha_client import HomeAssistantReadError

WEEK_OFFSET_LIMIT = 52
WEEK_EVENT_CAP = 300
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class CalendarReader(Protocol):
    async def get_calendar_events(
        self, entity_id: str, *, start: datetime, end: datetime
    ) -> list[dict]: ...


def local_midnight(day: date, zone: ZoneInfo) -> datetime:
    """Return the aware local midnight that starts ``day`` in ``zone``."""
    return datetime.combine(day, time.min, tzinfo=zone)


def local_window(first_day: date, days: int, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """Return [first_day 00:00, first_day+days 00:00) as aware local datetimes."""
    return local_midnight(first_day, zone), local_midnight(first_day + timedelta(days=days), zone)


def week_monday(today: date, week_offset: int) -> date:
    """Return the Monday of the ISO week ``week_offset`` weeks from ``today``."""
    return today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    calendar: str
    summary: str | None
    all_day: bool
    # UTC instants used for ordering and overlap. For all-day events these are
    # the local midnights of start_date and end_date_exclusive.
    start_utc: datetime
    end_utc: datetime
    start_date: date | None = None
    end_date_exclusive: date | None = None
    location: str | None = None

    def sort_key(self) -> tuple:
        return (self.start_utc, 0 if self.all_day else 1, self.summary or "", self.calendar)

    def overlaps(self, day_start_utc: datetime, day_end_utc: datetime) -> bool:
        if self.end_utc <= self.start_utc:
            # Instant (zero-length or end-less) event: belongs to the day it starts in.
            return day_start_utc <= self.start_utc < day_end_utc
        return self.start_utc < day_end_utc and self.end_utc > day_start_utc

    def as_dict(self, zone: ZoneInfo, *, include_locations: bool) -> dict:
        item: dict = {"calendar": self.calendar, "summary": self.summary, "all_day": self.all_day}
        if self.all_day:
            assert self.start_date is not None and self.end_date_exclusive is not None
            item["start_date"] = self.start_date.isoformat()
            # HA/iCalendar all-day end dates are exclusive: a one-day event on
            # the 5th ends on the 6th. last_date is the inclusive convenience.
            item["end_date_exclusive"] = self.end_date_exclusive.isoformat()
            item["last_date"] = (self.end_date_exclusive - timedelta(days=1)).isoformat()
        else:
            item["start"] = self.start_utc.astimezone(zone).isoformat()
            item["end"] = self.end_utc.astimezone(zone).isoformat()
        if include_locations and self.location:
            item["location"] = self.location
        return item


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _parse_instant(value: str, zone: ZoneInfo) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        # HA emits offsets; if one is ever missing, read it as configured-zone time.
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(UTC)


def _boundary(raw) -> tuple[str, str] | None:
    """Return ("date"|"dateTime", value) from an HA event start/end field."""
    if isinstance(raw, dict):
        if isinstance(raw.get("dateTime"), str):
            return "dateTime", raw["dateTime"]
        if isinstance(raw.get("date"), str):
            return "date", raw["date"]
        return None
    if isinstance(raw, str) and raw:
        # Tolerate bare strings: a 10-character value is a date.
        return ("date", raw) if len(raw) == 10 else ("dateTime", raw)
    return None


def normalize_event(entity_id: str, event: dict, zone: ZoneInfo) -> NormalizedEvent | None:
    """Normalize one HA calendar event, or return None if it is unusable.

    HA's ``GET /api/calendars/<entity>`` returns ``start``/``end`` as
    ``{"dateTime": "<ISO with offset>"}`` for timed events and
    ``{"date": "YYYY-MM-DD"}`` (end exclusive) for all-day events.
    Descriptions are never read.
    """
    start = _boundary(event.get("start"))
    if start is None:
        return None
    end = _boundary(event.get("end"))
    summary = event.get("summary")
    summary = summary if isinstance(summary, str) else None
    location = event.get("location")
    location = location if isinstance(location, str) and location else None
    try:
        if start[0] == "date":
            start_date = _parse_date(start[1])
            end_date = _parse_date(end[1]) if end is not None else start_date
            if end_date <= start_date:
                end_date = start_date + timedelta(days=1)
            return NormalizedEvent(
                calendar=entity_id,
                summary=summary,
                all_day=True,
                start_utc=local_midnight(start_date, zone).astimezone(UTC),
                end_utc=local_midnight(end_date, zone).astimezone(UTC),
                start_date=start_date,
                end_date_exclusive=end_date,
                location=location,
            )
        start_utc = _parse_instant(start[1], zone)
        if end is None:
            end_utc = start_utc
        elif end[0] == "date":
            end_utc = local_midnight(_parse_date(end[1]), zone).astimezone(UTC)
        else:
            end_utc = _parse_instant(end[1], zone)
        return NormalizedEvent(
            calendar=entity_id,
            summary=summary,
            all_day=False,
            start_utc=start_utc,
            end_utc=max(start_utc, end_utc),
            location=location,
        )
    except ValueError:
        return None


@dataclass(slots=True)
class CalendarFetch:
    """Per-calendar fetch outcome; one failure never hides the others."""

    events: list[NormalizedEvent]
    statuses: list[dict]

    @property
    def ok_count(self) -> int:
        return sum(1 for status in self.statuses if status["ok"])

    @property
    def all_failed(self) -> bool:
        return bool(self.statuses) and self.ok_count == 0

    @property
    def partial(self) -> bool:
        return 0 < self.ok_count < len(self.statuses)


async def fetch_calendars(
    client: CalendarReader,
    entity_ids: Sequence[str],
    start: datetime,
    end: datetime,
    zone: ZoneInfo,
) -> CalendarFetch:
    """Read every allowlisted calendar in parallel and normalize the events."""
    results = await asyncio.gather(
        *(client.get_calendar_events(entity_id, start=start, end=end) for entity_id in entity_ids),
        return_exceptions=True,
    )
    events: list[NormalizedEvent] = []
    statuses: list[dict] = []
    for entity_id, result in zip(entity_ids, results, strict=True):
        if isinstance(result, BaseException):
            if not isinstance(result, Exception):
                raise result
            # HomeAssistantReadError messages are already free of response
            # bodies; anything else is reduced to its type name.
            error = (
                str(result)
                if isinstance(result, HomeAssistantReadError)
                else f"calendar read failed: {type(result).__name__}"
            )
            statuses.append({"entity_id": entity_id, "ok": False, "error": error})
            continue
        normalized = [normalize_event(entity_id, event, zone) for event in result]
        usable = [event for event in normalized if event is not None]
        status = {"entity_id": entity_id, "ok": True, "event_count": len(usable)}
        if len(usable) != len(result):
            status["skipped_malformed"] = len(result) - len(usable)
        statuses.append(status)
        events.extend(usable)
    events.sort(key=NormalizedEvent.sort_key)
    return CalendarFetch(events=events, statuses=statuses)


def fetch_status_fields(fetch: CalendarFetch) -> dict:
    """Top-level status fields shared by the calendar tools."""
    if fetch.all_failed:
        return {
            "ok": False,
            "status": "error",
            "error": (
                "every allowlisted calendar failed to load; the schedule is unknown, "
                "not empty"
            ),
        }
    if fetch.partial:
        failed = [status["entity_id"] for status in fetch.statuses if not status["ok"]]
        return {
            "ok": True,
            "status": "partial",
            "warning": (
                "some calendars failed to load; events from them are missing: "
                + ", ".join(failed)
            ),
        }
    return {"ok": True, "status": "complete"}


async def build_week(
    client: CalendarReader,
    entity_ids: Sequence[str],
    zone: ZoneInfo,
    *,
    week_offset: int,
    include_locations: bool,
    now: datetime,
) -> dict:
    """Build the structured ISO-week (Monday-Sunday) calendar view."""
    today = now.astimezone(zone).date()
    monday = week_monday(today, week_offset)
    sunday = monday + timedelta(days=6)
    iso = monday.isocalendar()
    window_start, window_end = local_window(monday, 7, zone)
    header = {
        # ISO week-year, which differs from the calendar year around New Year
        # (e.g. 2024-12-30 is 2025-W01, 2021-01-03 is 2020-W53).
        "iso_year": iso.year,
        "iso_week": iso.week,
        "week_offset": week_offset,
        "start_date": monday.isoformat(),
        "end_date": sunday.isoformat(),
        "timezone": zone.key,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "retrieved_at": now.astimezone(zone).isoformat(),
    }

    fetch = await fetch_calendars(client, entity_ids, window_start, window_end, zone)
    status = fetch_status_fields(fetch)
    if not status["ok"]:
        return {**status, **header, "calendars": fetch.statuses}

    events = fetch.events[:WEEK_EVENT_CAP]
    days = []
    for index in range(7):
        day = monday + timedelta(days=index)
        day_start, day_end = local_window(day, 1, zone)
        day_start_utc, day_end_utc = day_start.astimezone(UTC), day_end.astimezone(UTC)
        all_day: list[dict] = []
        timed: list[dict] = []
        for event in events:
            if not event.overlaps(day_start_utc, day_end_utc):
                continue
            item = event.as_dict(zone, include_locations=include_locations)
            if event.all_day:
                all_day.append(item)
            else:
                item["starts_before_day"] = event.start_utc < day_start_utc
                item["ends_after_day"] = event.end_utc > day_end_utc
                timed.append(item)
        days.append(
            {
                "date": day.isoformat(),
                "weekday": WEEKDAYS[day.weekday()],
                "all_day": all_day,
                "events": timed,
            }
        )
    return {
        **status,
        **header,
        "calendars": fetch.statuses,
        "event_count": len(events),
        "truncated": len(fetch.events) > WEEK_EVENT_CAP,
        "days": days,
    }
