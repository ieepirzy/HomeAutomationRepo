"""Calendar tools: local windows, ISO weeks, DST, all-day semantics, failures."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import httpx
import pytest

from app import server
from app.calendar_view import build_week, local_window
from app.ha_client import HomeAssistantClient, HomeAssistantReadError

HELSINKI = ZoneInfo("Europe/Helsinki")
WORK = "calendar.work"
HOME = "calendar.home"


class FakeHA:
    """Stands in for HomeAssistantClient.get_calendar_events."""

    def __init__(self, events=None, failing=()):
        self.events = events or {}
        self.failing = set(failing)
        self.calls = []

    async def get_calendar_events(self, entity_id, *, start, end):
        self.calls.append((entity_id, start, end))
        if entity_id in self.failing:
            raise HomeAssistantReadError(
                f"Home Assistant read failed for /api/calendars/{entity_id}: HTTPStatusError"
            )
        return list(self.events.get(entity_id, []))


def timed(summary, start, end, **extra):
    return {"summary": summary, "start": {"dateTime": start}, "end": {"dateTime": end}, **extra}


def all_day(summary, start, end_exclusive, **extra):
    return {"summary": summary, "start": {"date": start}, "end": {"date": end_exclusive}, **extra}


@pytest.fixture
def use(monkeypatch):
    """Point the server module at a fake HA, an allowlist, a zone and a clock."""

    def apply(fake, *, now, entities=(WORK, HOME), timezone="Europe/Helsinki"):
        monkeypatch.setattr(
            server,
            "config",
            replace(server.config, calendar_entities=tuple(entities), timezone=timezone),
        )
        monkeypatch.setattr(server, "ha", fake)
        if now is not None:
            monkeypatch.setattr(server, "_now", lambda zone: now.astimezone(zone))
        return fake

    return apply


def day(result, iso_date):
    return next(item for item in result["days"] if item["date"] == iso_date)


def summaries(items):
    return [item["summary"] for item in items]


# --- week layout and offsets -------------------------------------------------


@pytest.mark.asyncio
async def test_ordinary_week_is_monday_to_sunday_in_configured_zone(use):
    fake = use(FakeHA(), now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI))

    result = await server.get_week()

    assert result["ok"] is True and result["status"] == "complete"
    assert (result["iso_year"], result["iso_week"]) == (2026, 39)
    assert (result["start_date"], result["end_date"]) == ("2026-09-21", "2026-09-27")
    assert result["timezone"] == "Europe/Helsinki"
    assert result["retrieved_at"] == "2026-09-24T12:00:00+03:00"
    assert [d["weekday"] for d in result["days"]] == [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    ]
    assert [d["date"] for d in result["days"]][0] == "2026-09-21"
    assert result["event_count"] == 0 and result["truncated"] is False
    # Both allowlisted calendars were queried for exactly the local week.
    assert {call[0] for call in fake.calls} == {WORK, HOME}
    for _, start, end in fake.calls:
        assert start.isoformat() == "2026-09-21T00:00:00+03:00"
        assert end.isoformat() == "2026-09-28T00:00:00+03:00"
    assert [s["ok"] for s in result["calendars"]] == [True, True]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("offset", "week", "monday"),
    [(-1, 38, "2026-09-14"), (-40, 51, "2025-12-15"), (2, 41, "2026-10-05"), (52, 38, "2027-09-20")]  # 2026 has 53 ISO weeks,
)
async def test_week_offsets(use, offset, week, monday):
    use(FakeHA(), now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI))

    result = await server.get_week(week_offset=offset)

    assert result["ok"] is True
    assert result["iso_week"] == week
    assert result["start_date"] == monday
    assert result["week_offset"] == offset


@pytest.mark.asyncio
@pytest.mark.parametrize("offset", [-53, 53, 1000])
async def test_week_offset_out_of_range_is_rejected(use, offset):
    fake = use(FakeHA(), now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI))

    result = await server.get_week(week_offset=offset)

    assert result == {"ok": False, "error": "week_offset must be between -52 and 52"}
    assert fake.calls == []


@pytest.mark.asyncio
async def test_week_offset_rejects_non_integers(use):
    use(FakeHA(), now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI))

    assert (await server.get_week(week_offset=True))["ok"] is False
    assert (await server.get_week(week_offset=1.5))["ok"] is False


# --- ISO week-year boundaries -----------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("now", "offset", "iso_year", "iso_week", "start", "end"),
    [
        # Week-year AFTER calendar year: 2024-12-30 is 2025-W01.
        (datetime(2024, 12, 31, 9, 0), 0, 2025, 1, "2024-12-30", "2025-01-05"),
        # Week-year BEFORE calendar year: 2021-01-03 is 2020-W53.
        (datetime(2021, 1, 2, 9, 0), 0, 2020, 53, "2020-12-28", "2021-01-03"),
        # 2026 has 53 ISO weeks; 2027-01-01 still belongs to 2026-W53.
        (datetime(2027, 1, 1, 9, 0), 0, 2026, 53, "2026-12-28", "2027-01-03"),
        # Offsets cross the boundary in both directions.
        (datetime(2026, 12, 30, 9, 0), 1, 2027, 1, "2027-01-04", "2027-01-10"),
        (datetime(2027, 1, 6, 9, 0), -1, 2026, 53, "2026-12-28", "2027-01-03"),
    ],
)
async def test_iso_week_year_boundaries(use, now, offset, iso_year, iso_week, start, end):
    use(FakeHA(), now=now.replace(tzinfo=HELSINKI))

    result = await server.get_week(week_offset=offset)

    assert (result["iso_year"], result["iso_week"]) == (iso_year, iso_week)
    assert (result["start_date"], result["end_date"]) == (start, end)


@pytest.mark.asyncio
async def test_today_is_taken_in_configured_zone_not_utc(use):
    # Monday 01:30 in Helsinki is still Sunday in UTC (previous ISO week).
    use(FakeHA(), now=datetime(2026, 9, 20, 22, 30, tzinfo=UTC))

    result = await server.get_week()

    assert (result["iso_week"], result["start_date"]) == (39, "2026-09-21")


# --- DST --------------------------------------------------------------------


def test_dst_days_are_23_and_25_hours_long():
    spring_start, spring_end = local_window(date(2026, 3, 29), 1, HELSINKI)
    autumn_start, autumn_end = local_window(date(2026, 10, 25), 1, HELSINKI)
    # Compare in UTC: same-zone aware subtraction is wall-clock in Python.
    assert spring_end.astimezone(UTC) - spring_start.astimezone(UTC) == timedelta(hours=23)
    assert autumn_end.astimezone(UTC) - autumn_start.astimezone(UTC) == timedelta(hours=25)
    assert spring_start.utcoffset() == timedelta(hours=2)
    assert spring_end.utcoffset() == timedelta(hours=3)


@pytest.mark.asyncio
async def test_spring_forward_week_queries_correct_utc_instants(use):
    fake = use(
        FakeHA(
            {
                WORK: [
                    # Sunday 23:30 EEST is still Sunday; Monday 00:30 is next week.
                    timed("late sunday", "2026-03-29T23:30:00+03:00", "2026-03-29T23:45:00+03:00"),
                    timed("before switch", "2026-03-29T02:30:00+02:00", "2026-03-29T02:45:00+02:00"),
                ]
            }
        ),
        now=datetime(2026, 3, 25, 12, 0, tzinfo=HELSINKI),
        entities=(WORK,),
    )

    result = await server.get_week()

    _, start, end = fake.calls[0]
    assert start.astimezone(UTC) == datetime(2026, 3, 22, 22, 0, tzinfo=UTC)
    assert end.astimezone(UTC) == datetime(2026, 3, 29, 21, 0, tzinfo=UTC)
    assert (end.astimezone(UTC) - start.astimezone(UTC)) == timedelta(hours=167)
    sunday = day(result, "2026-03-29")
    assert summaries(sunday["events"]) == ["before switch", "late sunday"]
    assert sunday["events"][1]["start"] == "2026-03-29T23:30:00+03:00"


@pytest.mark.asyncio
async def test_fall_back_week_orders_repeated_hour_by_instant(use):
    fake = use(
        FakeHA(
            {
                WORK: [
                    # 03:30 occurs twice on 2026-10-25; the +02:00 one is later.
                    timed("alpha (later, EET)", "2026-10-25T03:30:00+02:00", "2026-10-25T03:45:00+02:00"),
                    timed("beta (earlier, EEST)", "2026-10-25T03:30:00+03:00", "2026-10-25T03:45:00+03:00"),
                    timed("sunday 23:30", "2026-10-25T23:30:00+02:00", "2026-10-25T23:59:00+02:00"),
                ]
            }
        ),
        now=datetime(2026, 10, 20, 12, 0, tzinfo=HELSINKI),
        entities=(WORK,),
    )

    result = await server.get_week()

    _, start, end = fake.calls[0]
    assert start.astimezone(UTC) == datetime(2026, 10, 18, 21, 0, tzinfo=UTC)
    assert end.astimezone(UTC) == datetime(2026, 10, 25, 22, 0, tzinfo=UTC)
    sunday = day(result, "2026-10-25")
    assert summaries(sunday["events"]) == ["beta (earlier, EEST)", "alpha (later, EET)", "sunday 23:30"]
    assert [e["start"] for e in sunday["events"][:2]] == [
        "2026-10-25T03:30:00+03:00",
        "2026-10-25T03:30:00+02:00",
    ]
    assert day(result, "2026-10-24")["events"] == []


# --- event semantics ----------------------------------------------------------


@pytest.mark.asyncio
async def test_all_day_events_use_exclusive_end_dates(use):
    use(
        FakeHA(
            {
                HOME: [
                    all_day("single", "2026-09-23", "2026-09-24"),
                    all_day("trip", "2026-09-25", "2026-09-28"),
                    all_day("started last week", "2026-09-19", "2026-09-22"),
                ]
            }
        ),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI),
        entities=(HOME,),
    )

    result = await server.get_week()

    assert summaries(day(result, "2026-09-21")["all_day"]) == ["started last week"]
    assert summaries(day(result, "2026-09-22")["all_day"]) == []
    assert summaries(day(result, "2026-09-23")["all_day"]) == ["single"]
    assert summaries(day(result, "2026-09-24")["all_day"]) == []
    for iso in ("2026-09-25", "2026-09-26", "2026-09-27"):
        assert summaries(day(result, iso)["all_day"]) == ["trip"]
    trip = day(result, "2026-09-26")["all_day"][0]
    assert trip == {
        "calendar": HOME,
        "summary": "trip",
        "all_day": True,
        "start_date": "2026-09-25",
        "end_date_exclusive": "2026-09-28",
        "last_date": "2026-09-27",
    }
    assert result["event_count"] == 3


@pytest.mark.asyncio
async def test_timed_event_spanning_midnight_appears_on_both_days(use):
    use(
        FakeHA({WORK: [timed("night shift", "2026-09-25T22:00:00+03:00", "2026-09-26T02:00:00+03:00")]}),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI),
        entities=(WORK,),
    )

    result = await server.get_week()

    friday = day(result, "2026-09-25")["events"]
    saturday = day(result, "2026-09-26")["events"]
    assert summaries(friday) == summaries(saturday) == ["night shift"]
    assert (friday[0]["starts_before_day"], friday[0]["ends_after_day"]) == (False, True)
    assert (saturday[0]["starts_before_day"], saturday[0]["ends_after_day"]) == (True, False)
    assert friday[0]["start"] == "2026-09-25T22:00:00+03:00"
    assert friday[0]["end"] == "2026-09-26T02:00:00+03:00"
    # An event ending exactly at midnight does not leak into the next day.
    assert day(result, "2026-09-27")["events"] == []


@pytest.mark.asyncio
async def test_events_sort_by_instant_across_formats_and_calendars(use):
    use(
        FakeHA(
            {
                WORK: [
                    timed("nine utc-z", "2026-09-25T06:00:00Z", "2026-09-25T07:00:00Z"),
                    timed("eight", "2026-09-25T08:00:00+03:00", "2026-09-25T08:30:00+03:00"),
                ],
                HOME: [
                    timed("ten", "2026-09-25T10:00:00+03:00", "2026-09-25T11:00:00+03:00"),
                    all_day("holiday", "2026-09-25", "2026-09-26"),
                ],
            }
        ),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI),
    )

    week = await server.get_week()
    listing = await server.get_calendar_events(day_offset=1, days=1)

    friday = day(week, "2026-09-25")
    assert summaries(friday["events"]) == ["eight", "nine utc-z", "ten"]
    assert summaries(friday["all_day"]) == ["holiday"]
    # Output timestamps are rendered in the configured zone.
    assert friday["events"][1]["start"] == "2026-09-25T09:00:00+03:00"
    # get_calendar_events: all-day first, then timed by instant (not by string).
    assert summaries(listing["events"]) == ["holiday", "eight", "nine utc-z", "ten"]


@pytest.mark.asyncio
async def test_locations_are_opt_in_and_descriptions_never_leave(use):
    event = timed(
        "dentist",
        "2026-09-24T15:00:00+03:00",
        "2026-09-24T16:00:00+03:00",
        location="Hämeenkatu 1",
        description="private notes",
        uid="abc",
    )
    use(FakeHA({WORK: [event]}), now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI), entities=(WORK,))

    without = day(await server.get_week(), "2026-09-24")["events"][0]
    with_loc = day(await server.get_week(include_locations=True), "2026-09-24")["events"][0]
    listing = await server.get_calendar_events(day_offset=0, include_locations=True)

    assert "location" not in without
    assert with_loc["location"] == "Hämeenkatu 1"
    assert listing["events"][0]["location"] == "Hämeenkatu 1"
    for item in (without, with_loc, listing["events"][0]):
        assert "description" not in item and "uid" not in item
        assert "private notes" not in repr(item)


@pytest.mark.asyncio
async def test_malformed_events_are_skipped_and_counted(use):
    use(
        FakeHA({WORK: [{"summary": "no start"}, timed("ok", "2026-09-24T15:00:00+03:00", "2026-09-24T16:00:00+03:00")]}),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI),
        entities=(WORK,),
    )

    result = await server.get_week()

    assert result["calendars"] == [
        {"entity_id": WORK, "ok": True, "event_count": 1, "skipped_malformed": 1}
    ]
    assert result["event_count"] == 1


@pytest.mark.asyncio
async def test_week_is_capped_at_300_events(use):
    events = [
        timed(f"e{i:03}", f"2026-09-24T{10 + i // 60:02}:{i % 60:02}:00+03:00", f"2026-09-24T20:00:00+03:00")
        for i in range(301)
    ]
    use(FakeHA({WORK: events}), now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI), entities=(WORK,))

    result = await server.get_week()

    assert result["truncated"] is True
    assert result["event_count"] == 300
    assert summaries(day(result, "2026-09-24")["events"])[-1] == "e299"


# --- failures and allowlist ---------------------------------------------------


@pytest.mark.asyncio
async def test_one_failing_calendar_returns_partial_results(use):
    use(
        FakeHA(
            {HOME: [timed("gym", "2026-09-24T18:00:00+03:00", "2026-09-24T19:00:00+03:00")]},
            failing={WORK},
        ),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI),
    )

    week = await server.get_week()
    listing = await server.get_calendar_events(day_offset=0)

    for result in (week, listing):
        assert result["ok"] is True
        assert result["status"] == "partial"
        assert WORK in result["warning"]
        failed = next(s for s in result["calendars"] if s["entity_id"] == WORK)
        assert failed["ok"] is False and "HTTPStatusError" in failed["error"]
    assert summaries(day(week, "2026-09-24")["events"]) == ["gym"]
    assert summaries(listing["events"]) == ["gym"]


@pytest.mark.asyncio
async def test_all_calendars_failing_is_an_error_not_a_free_week(use):
    use(FakeHA(failing={WORK, HOME}), now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI))

    week = await server.get_week()
    listing = await server.get_calendar_events()

    for result in (week, listing):
        assert result["ok"] is False
        assert result["status"] == "error"
        assert "unknown, not empty" in result["error"]
        assert "days" not in result and "events" not in result
        assert [s["ok"] for s in result["calendars"]] == [False, False]
    assert (week["iso_week"], week["start_date"]) == (39, "2026-09-21")


@pytest.mark.asyncio
async def test_unexpected_exception_is_reduced_to_type_name(use):
    class Boom(FakeHA):
        async def get_calendar_events(self, entity_id, *, start, end):
            raise KeyError("secret event text")

    use(Boom(), now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI), entities=(WORK,))

    result = await server.get_week()

    assert result["calendars"] == [
        {"entity_id": WORK, "ok": False, "error": "calendar read failed: KeyError"}
    ]


@pytest.mark.asyncio
async def test_no_allowlist_means_no_reads(use):
    fake = use(FakeHA(), now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI), entities=())

    for result in (await server.get_week(), await server.get_calendar_events()):
        assert result == {"ok": False, "error": "no Home Assistant calendars are allowlisted"}
    assert fake.calls == []


@pytest.mark.asyncio
async def test_only_allowlisted_calendars_are_queried(use):
    fake = use(
        FakeHA({"calendar.secret": [timed("x", "2026-09-24T15:00:00+03:00", "2026-09-24T16:00:00+03:00")]}),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=HELSINKI),
        entities=(WORK,),
    )

    result = await server.get_week()

    assert [call[0] for call in fake.calls] == [WORK]
    assert result["event_count"] == 0


# --- get_calendar_events uses the configured zone ------------------------------


@pytest.mark.asyncio
async def test_get_calendar_events_uses_configured_zone(use):
    # 02:00 UTC on the 24th is still the 23rd in New York, so "tomorrow" is the 24th.
    fake = use(
        FakeHA(),
        now=datetime(2026, 9, 24, 2, 0, tzinfo=UTC),
        entities=(WORK,),
        timezone="America/New_York",
    )

    result = await server.get_calendar_events(day_offset=1, days=1)

    assert result["timezone"] == "America/New_York"
    assert result["start"] == "2026-09-24T00:00:00-04:00"
    assert result["end"] == "2026-09-25T00:00:00-04:00"
    _, start, end = fake.calls[0]
    assert start.astimezone(UTC) == datetime(2026, 9, 24, 4, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_get_calendar_events_real_clock_uses_configured_zone(use):
    # No clock seam: the real wall clock, a zone unlike any likely host zone.
    use(FakeHA(), now=None, entities=(WORK,), timezone="Pacific/Chatham")

    result = await server.get_calendar_events(day_offset=0, days=1)

    start = datetime.fromisoformat(result["start"])
    assert result["timezone"] == "Pacific/Chatham"
    assert start.utcoffset() in (timedelta(hours=12, minutes=45), timedelta(hours=13, minutes=45))
    assert (start.hour, start.minute) == (0, 0)
    assert start.date() == datetime.now(ZoneInfo("Pacific/Chatham")).date()


@pytest.mark.asyncio
async def test_get_calendar_events_dst_window_is_23_hours(use):
    fake = use(
        FakeHA(), now=datetime(2026, 3, 28, 12, 0, tzinfo=HELSINKI), entities=(WORK,)
    )

    result = await server.get_calendar_events(day_offset=1, days=1)

    assert result["start"] == "2026-03-29T00:00:00+02:00"
    assert result["end"] == "2026-03-30T00:00:00+03:00"
    _, start, end = fake.calls[0]
    assert end.astimezone(UTC) - start.astimezone(UTC) == timedelta(hours=23)


# --- the real HTTP client ---------------------------------------------------------


@pytest.mark.asyncio
async def test_real_client_sends_offset_instants_through_url_encoding():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("calendar.broken"):
            return httpx.Response(500, text="private event body")
        return httpx.Response(
            200,
            json=[
                {
                    "summary": "flight",
                    "start": {"dateTime": "2026-10-25T03:30:00+02:00"},
                    "end": {"dateTime": "2026-10-25T05:00:00+02:00"},
                    "description": "booking ref",
                }
            ],
        )

    client = HomeAssistantClient(
        base_url="http://ha.test", token="t", timeout_seconds=1, transport=httpx.MockTransport(handler)
    )
    result = await build_week(
        client,
        ("calendar.ok", "calendar.broken"),
        HELSINKI,
        week_offset=0,
        include_locations=False,
        now=datetime(2026, 10, 21, 8, 0, tzinfo=HELSINKI),
    )

    ok_request = next(r for r in seen if r.url.path == "/api/calendars/calendar.ok")
    assert b"%2B03%3A00" in ok_request.url.query  # '+' must not arrive as a space
    params = parse_qs(urlsplit(str(ok_request.url)).query)
    assert datetime.fromisoformat(params["start"][0]).astimezone(UTC) == datetime(
        2026, 10, 18, 21, 0, tzinfo=UTC
    )
    assert datetime.fromisoformat(params["end"][0]).astimezone(UTC) == datetime(
        2026, 10, 25, 22, 0, tzinfo=UTC
    )
    assert result["status"] == "partial"
    broken = next(s for s in result["calendars"] if s["entity_id"] == "calendar.broken")
    assert "private event body" not in broken["error"]
    sunday = day(result, "2026-10-25")["events"]
    assert sunday == [
        {
            "calendar": "calendar.ok",
            "summary": "flight",
            "all_day": False,
            "start": "2026-10-25T03:30:00+02:00",
            "end": "2026-10-25T05:00:00+02:00",
            "starts_before_day": False,
            "ends_after_day": False,
        }
    ]
