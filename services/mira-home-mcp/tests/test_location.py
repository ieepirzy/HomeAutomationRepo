from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "app" / "location.py"
SPEC = spec_from_file_location("mira_home_location", MODULE_PATH)
location = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(location)


def test_coordinates_resolve_all_overlapping_zones():
    tracker = {
        "state": "home",
        "attributes": {"latitude": 61.5000, "longitude": 23.7880},
    }
    states = [
        {
            "entity_id": "zone.home",
            "attributes": {
                "friendly_name": "Home",
                "latitude": 61.4991,
                "longitude": 23.7871,
                "radius": 200,
            },
        },
        {
            "entity_id": "zone.neighborhood",
            "attributes": {
                "friendly_name": "Neighborhood",
                "latitude": 61.4991,
                "longitude": 23.7871,
                "radius": 1000,
                "passive": True,
            },
        },
    ]

    result = location.matching_zones(tracker, states)

    assert [zone["name"] for zone in result] == ["Home", "Neighborhood"]
    assert all("latitude" not in zone and "longitude" not in zone for zone in result)


def test_zone_name_only_mode_uses_tracker_state():
    tracker = {"state": "university", "attributes": {}}
    states = [
        {
            "entity_id": "zone.university",
            "attributes": {"friendly_name": "University", "passive": False},
        }
    ]

    assert location.matching_zones(tracker, states) == [
        {"entity_id": "zone.university", "name": "University", "passive": False}
    ]


def test_speed_is_reported_without_claiming_driving():
    result = location.speed_summary({"attributes": {"speed": 10}})

    assert result["kilometers_per_hour"] == 36.0
    assert result["motion"] == "fast_moving"
    assert "does not prove" in result["note"]


def test_address_filters_coordinate_like_attributes():
    result = location.sanitized_address(
        {
            "state": "Example Street 1",
            "attributes": {
                "Locality": "Tampere",
                "Postal Code": "33100",
                "Latitude": 61.5,
                "Longitude": 23.7,
            },
        }
    )

    assert result["display"] == "Example Street 1"
    assert result["details"] == {"Locality": "Tampere", "Postal Code": "33100"}
    assert result["observed_at"] is None
    assert result["age_seconds"] is None


def test_coordinates_include_accuracy_and_motion_metadata():
    result = location.coordinates_summary(
        {
            "attributes": {
                "latitude": 61.5,
                "longitude": 23.7,
                "gps_accuracy": 12,
                "altitude": 105.5,
                "course": 180,
            }
        }
    )

    assert result == {
        "latitude": 61.5,
        "longitude": 23.7,
        "accuracy_m": 12.0,
        "altitude_m": 105.5,
        "course_degrees": 180.0,
    }


def test_activity_preserves_companion_classification_and_freshness():
    now = datetime.now(timezone.utc)
    result = location.activity_summary(
        {
            "state": "Automotive",
            "last_updated": now.isoformat(),
            "attributes": {"confidence": "High", "types": ["Automotive"]},
        }
    )

    assert result["state"] == "automotive"
    assert result["confidence"] == "High"
    assert result["types"] == ["Automotive"]
    assert result["age_seconds"] == 0


def test_age_seconds_is_utc_safe():
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    assert location.age_seconds("2026-08-23T11:58:30+00:00", now) == 90
