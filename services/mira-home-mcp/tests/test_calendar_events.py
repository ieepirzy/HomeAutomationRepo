from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "app" / "calendar_events.py"
SPEC = spec_from_file_location("mira_home_calendar_events", MODULE_PATH)
calendar_events = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(calendar_events)


def test_description_and_location_always_included():
    event = {
        "summary": "Sannin synttärit",
        "start": {"dateTime": "2026-09-27T18:00:00+03:00"},
        "end": {"dateTime": "2026-09-27T21:00:00+03:00"},
        "location": "Kauppakatu 1, Jyväskylä",
        "description": "Teema: 80-luku. Ota lahja.",
    }
    item = calendar_events.shape_event("calendar.koti", event)
    assert item == {
        "calendar": "calendar.koti",
        "summary": "Sannin synttärit",
        "start": event["start"],
        "end": event["end"],
        "location": "Kauppakatu 1, Jyväskylä",
        "description": "Teema: 80-luku. Ota lahja.",
    }


def test_empty_fields_are_left_out_and_long_descriptions_capped():
    item = calendar_events.shape_event(
        "calendar.tyo", {"summary": "x", "location": "  ", "description": None})
    assert "location" not in item and "description" not in item
    long = calendar_events.shape_event("calendar.tyo", {"description": "a" * 5000})
    assert len(long["description"]) == calendar_events.DESCRIPTION_LIMIT + 1
