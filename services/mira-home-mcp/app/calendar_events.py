"""Shape Home Assistant calendar events for Mira.

Descriptions and locations are always included: only Ilari (and the feeds he
chose to subscribe to) can put events on the allowlisted calendars, and the
details (addresses, prep notes, assignment text) are what Mira needs to plan
leave and prep times.
"""

from __future__ import annotations

DESCRIPTION_LIMIT = 4000


def shape_event(calendar: str, event: dict) -> dict:
    item = {
        "calendar": calendar,
        "summary": event.get("summary"),
        "start": event.get("start"),
        "end": event.get("end"),
    }
    location = (event.get("location") or "").strip()
    if location:
        item["location"] = location
    description = (event.get("description") or "").strip()
    if description:
        if len(description) > DESCRIPTION_LIMIT:
            description = description[:DESCRIPTION_LIMIT] + "…"
        item["description"] = description
    return item
