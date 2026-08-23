"""Pure helpers for turning Home Assistant phone state into Mira context."""

from __future__ import annotations

from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any

EARTH_RADIUS_METERS = 6_371_000.0


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two WGS84 points."""
    lat1r, lon1r, lat2r, lon2r = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = sin(dlat / 2) ** 2 + cos(lat1r) * cos(lat2r) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * asin(sqrt(a))


def matching_zones(location: dict, states: list[dict]) -> list[dict]:
    """Resolve every matching HA zone without returning source coordinates."""
    attrs = location.get("attributes") or {}
    latitude = _number(attrs.get("latitude"))
    longitude = _number(attrs.get("longitude"))
    if latitude is None or longitude is None:
        return _state_named_zone(location, states)

    matches: list[dict] = []
    for state in states:
        entity_id = str(state.get("entity_id", ""))
        if not entity_id.startswith("zone."):
            continue
        zone_attrs = state.get("attributes") or {}
        zone_lat = _number(zone_attrs.get("latitude"))
        zone_lon = _number(zone_attrs.get("longitude"))
        radius = _number(zone_attrs.get("radius"))
        if zone_lat is None or zone_lon is None or radius is None:
            continue
        distance = distance_meters(latitude, longitude, zone_lat, zone_lon)
        if distance <= radius:
            matches.append(
                {
                    "entity_id": entity_id,
                    "name": zone_attrs.get("friendly_name") or entity_id.removeprefix("zone."),
                    "distance_from_center_m": round(distance),
                    "radius_m": round(radius),
                    "passive": bool(zone_attrs.get("passive", False)),
                }
            )
    return sorted(matches, key=lambda zone: zone["distance_from_center_m"])


def _state_named_zone(location: dict, states: list[dict]) -> list[dict]:
    state_name = str(location.get("state", ""))
    if state_name in {"", "not_home", "unknown", "unavailable"}:
        return []
    for state in states:
        if state.get("entity_id") == f"zone.{state_name}":
            attrs = state.get("attributes") or {}
            return [
                {
                    "entity_id": state["entity_id"],
                    "name": attrs.get("friendly_name") or state_name,
                    "passive": bool(attrs.get("passive", False)),
                }
            ]
    return [{"entity_id": None, "name": state_name, "passive": False}]


def speed_summary(location: dict) -> dict | None:
    """Return speed and a cautious motion label; never assert transportation mode."""
    attrs = location.get("attributes") or {}
    meters_per_second = _number(attrs.get("speed"))
    if meters_per_second is None:
        return None
    kilometers_per_hour = max(0.0, meters_per_second * 3.6)
    if kilometers_per_hour < 1:
        motion = "stationary"
    elif kilometers_per_hour < 15:
        motion = "moving"
    else:
        motion = "fast_moving"
    return {
        "meters_per_second": round(max(0.0, meters_per_second), 2),
        "kilometers_per_hour": round(kilometers_per_hour, 1),
        "motion": motion,
        "note": "speed alone does not prove that the person is driving",
    }


def coordinates_summary(location: dict) -> dict | None:
    """Return Companion tracker coordinates and quality metadata when present."""
    attrs = location.get("attributes") or {}
    latitude = _number(attrs.get("latitude"))
    longitude = _number(attrs.get("longitude"))
    if latitude is None or longitude is None:
        return None
    result: dict[str, float] = {"latitude": latitude, "longitude": longitude}
    for source, target in (
        ("gps_accuracy", "accuracy_m"),
        ("altitude", "altitude_m"),
        ("course", "course_degrees"),
    ):
        value = _number(attrs.get(source))
        if value is not None:
            result[target] = value
    return result


def activity_summary(state: dict | None) -> dict | None:
    """Return the Companion activity sensor without inventing a movement mode."""
    if not state or state.get("state") in {None, "", "unknown", "unavailable"}:
        return None
    attrs = state.get("attributes") or {}
    result = {
        "state": str(state["state"]).strip().lower(),
        "observed_at": state.get("last_updated"),
        "age_seconds": age_seconds(state.get("last_updated")),
    }
    if attrs.get("confidence") is not None:
        result["confidence"] = attrs["confidence"]
    if attrs.get("types") is not None:
        result["types"] = attrs["types"]
    return result


def age_seconds(timestamp: str | None, now: datetime | None = None) -> int | None:
    if not timestamp:
        return None
    try:
        observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0, round((current - observed.astimezone(timezone.utc)).total_seconds()))


ADDRESS_ATTRIBUTE_ALLOWLIST = (
    "Name",
    "Thoroughfare",
    "Sub Thoroughfare",
    "Sub Locality",
    "Locality",
    "Sub Administrative Area",
    "Administrative Area",
    "Postal Code",
    "Country",
    "ISO Country Code",
    "Time Zone",
)


def sanitized_address(state: dict) -> dict | None:
    value = state.get("state")
    if value in {None, "", "unknown", "unavailable"}:
        return None
    attrs = state.get("attributes") or {}
    details = {key: attrs[key] for key in ADDRESS_ATTRIBUTE_ALLOWLIST if attrs.get(key)}
    return {
        "display": value,
        "details": details,
        "observed_at": state.get("last_updated"),
        "age_seconds": age_seconds(state.get("last_updated")),
    }
