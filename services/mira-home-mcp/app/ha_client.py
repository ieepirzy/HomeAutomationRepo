"""Small, read-only client for the Home Assistant REST API."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import httpx


class HomeAssistantReadError(RuntimeError):
    """A Home Assistant read could not be completed."""


class HomeAssistantClient:
    def __init__(self, *, base_url: str, token: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = timeout_seconds

    async def _get(self, path: str, *, params: dict[str, str] | None = None):
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}{path}", headers=self._headers, params=params
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Do not include response bodies: an upstream error can echo private
            # state, and tool errors are routinely copied into model context.
            raise HomeAssistantReadError(
                f"Home Assistant read failed for {path}: {type(exc).__name__}"
            ) from exc

    async def get_state(self, entity_id: str) -> dict:
        return await self._get(f"/api/states/{quote(entity_id, safe='.')}")

    async def list_states(self) -> list[dict]:
        result = await self._get("/api/states")
        if not isinstance(result, list):
            raise HomeAssistantReadError("Home Assistant returned a non-list state response")
        return result

    async def get_calendar_events(
        self, entity_id: str, *, start: datetime, end: datetime
    ) -> list[dict]:
        result = await self._get(
            f"/api/calendars/{quote(entity_id, safe='.')}",
            params={"start": start.isoformat(), "end": end.isoformat()},
        )
        if not isinstance(result, list):
            raise HomeAssistantReadError(
                f"Home Assistant returned a non-list calendar response for {entity_id}"
            )
        return result
