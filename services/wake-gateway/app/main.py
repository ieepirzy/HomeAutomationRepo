"""Wake gateway — the Python webhook server iOS Shortcuts talks to.

This exists as its own standalone service (rather than using Home
Assistant's built-in webhook automation trigger, which could equally
have handled this) per explicit design preference — see
docs/wakeup-protocol.md "Wake gateway" for the tradeoff notes. It is the
adapter boundary from spec section 8: Shortcuts hits a plain `GET` here,
the gateway normalizes that into Home Assistant's event bus via HA's
REST API, and every downstream automation only ever consumes the
normalized `ila_wake_detected` / `ila_phone_undocked` events — nothing
about Shortcuts or this gateway leaks past this file.

Two GET endpoints, one per signal, both single-segment path tokens
(acting as bearer secrets, same convention as Home Assistant's own
webhook_id) so the corresponding iOS Shortcut is just a single "Get
Contents of URL" action with no headers or body to configure.
"""

import logging
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Response

from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("wake_gateway.main")

app = FastAPI(title="Wake-Up Protocol Gateway")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/wake/{token}")
async def wake(token: str):
    _check_token(token, config.WAKE_TOKEN, "wake")
    await _fire_ha_event("ila_wake_detected", {"source": "apple_watch"})
    return Response(content="OK", media_type="text/plain")


@app.get("/undock/{token}")
async def undock(token: str):
    _check_token(token, config.UNDOCK_TOKEN, "undock")
    await _fire_ha_event("ila_phone_undocked", {"source": "shortcut"})
    return Response(content="OK", media_type="text/plain")


def _check_token(provided: str, expected: str, label: str) -> None:
    # constant-time compare — this token is the entire auth mechanism
    # for these endpoints, same threat model as an HA webhook_id.
    if not secrets.compare_digest(provided, expected):
        logger.warning("rejected %s request: bad token", label)
        raise HTTPException(status_code=404)  # 404, not 401 — don't confirm the path exists


async def _fire_ha_event(event_type: str, event_data: dict) -> None:
    """POSTs to Home Assistant's built-in REST API to fire a normalized
    bus event — the exact mechanism `homeassistant/packages/wakeup_protocol.yaml`
    consumes via `trigger: event`. See
    https://developers.home-assistant.io/docs/api/rest/#post-apieventsevent_type
    """
    payload = {**event_data, "detected_at": datetime.now(timezone.utc).isoformat()}
    url = f"{config.HA_BASE_URL.rstrip('/')}/api/events/{event_type}"

    try:
        async with httpx.AsyncClient(timeout=config.HA_REQUEST_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {config.HA_LONG_LIVED_TOKEN}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
        logger.info("fired %s (source=%s)", event_type, event_data.get("source"))
    except httpx.HTTPError as exc:
        logger.error("failed to fire %s on Home Assistant: %s", event_type, exc)
        # 502: the gateway itself is fine, but it couldn't reach HA. A
        # non-2xx response lets the Shortcut surface a failure instead of
        # silently believing the wake/undock signal was delivered.
        raise HTTPException(status_code=502, detail="could not reach Home Assistant") from exc
