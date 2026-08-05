"""Weather lookup for the briefing. Best-effort only — per the wake-up
protocol spec, if weather is unavailable the section is omitted from the
briefing rather than inventing data. Never raises; returns None on any
failure so callers can branch on that directly."""

import logging
from typing import Optional

import httpx

from . import config

logger = logging.getLogger("briefing.weather")


async def get_weather_summary() -> Optional[str]:
    if not config.OPENWEATHER_API_KEY:
        return None

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            current_resp = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "lat": config.HOME_LAT,
                    "lon": config.HOME_LON,
                    "appid": config.OPENWEATHER_API_KEY,
                    "units": "metric",
                },
            )
            current_resp.raise_for_status()
            current = current_resp.json()

            forecast_resp = await client.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={
                    "lat": config.HOME_LAT,
                    "lon": config.HOME_LON,
                    "appid": config.OPENWEATHER_API_KEY,
                    "units": "metric",
                },
            )
            forecast_resp.raise_for_status()
            forecast = forecast_resp.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("weather lookup failed, omitting from briefing: %s", exc)
        return None

    try:
        temp_c = round(current["main"]["temp"])
        description = current["weather"][0]["description"]
        summary = f"{temp_c} degrees Celsius, {description}"

        rain_hint = _rain_hint_from_forecast(forecast)
        if rain_hint:
            summary += f", {rain_hint}"
        return summary
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("weather response malformed, omitting from briefing: %s", exc)
        return None


def _rain_hint_from_forecast(forecast: dict) -> Optional[str]:
    """Look at today's remaining 3-hour forecast blocks and, if rain first
    appears at some point, return a short "rain expected after HH:MM"
    hint. Returns None if no rain is forecast today or the data is odd —
    never invents a time."""
    try:
        entries = forecast.get("list", [])
        for entry in entries[:8]:  # next ~24h in 3h steps
            weather_list = entry.get("weather", [])
            has_rain = any(w.get("main", "").lower() in ("rain", "drizzle", "thunderstorm") for w in weather_list)
            if has_rain:
                dt_txt = entry.get("dt_txt", "")  # "2026-08-05 16:00:00"
                if dt_txt:
                    time_part = dt_txt.split(" ")[1][:5]
                    return f"rain expected after {time_part}"
                return "rain expected later today"
        return None
    except (AttributeError, IndexError, TypeError):
        return None
