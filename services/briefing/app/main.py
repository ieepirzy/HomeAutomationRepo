"""Briefing service — generates the AI morning briefing (text + optional
TTS audio) out-of-band from Home Assistant's wake flow.

POST /generate returns 202 immediately and does the actual work in a
background task, then POSTs the result to the callback_url Home
Assistant supplied (the ila_briefing_ready webhook). This is the
mechanism that lets generation start at alarm time without ever blocking
lights/alarm — see docs/wakeup-protocol.md "AI Morning Briefing".

Every failure mode (LLM error/refusal, TTS error, weather unavailable,
network failure reaching HA) is caught and reported as a best-effort
"failed" callback rather than left to hang or crash the process — a
broken briefing must never break the wake-up flow it's decorating.
"""

import logging
import time
from typing import Optional

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import config, tts
from .briefing import BriefingInputs, generate_briefing_text
from .weather import get_weather_summary

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("briefing.main")

app = FastAPI(title="Wake-Up Protocol Briefing Service")


class GenerateRequest(BaseModel):
    session_id: str
    callback_url: str
    test_mode: bool = False
    current_streak: Optional[int] = None
    priorities: list[str] = []
    name: str = "Ila"


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/generate", status_code=202)
async def generate(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    authorization: str = Header(default=""),
):
    expected = f"Bearer {config.BRIEFING_AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="invalid or missing bearer token")

    logger.info("[%s] briefing generation accepted (test_mode=%s)", req.session_id, req.test_mode)
    background_tasks.add_task(_generate_and_report, req)
    return {"status": "accepted", "session_id": req.session_id}


async def _generate_and_report(req: GenerateRequest) -> None:
    started_at = time.monotonic()
    status = "failed"
    text = ""
    audio_url: Optional[str] = None

    try:
        weather_summary = None if req.test_mode else await get_weather_summary()

        inputs = BriefingInputs(
            name=req.name,
            current_streak=req.current_streak,
            weather_summary=weather_summary,
            priorities=req.priorities,
        )
        text, used_llm = await generate_briefing_text(inputs)
        logger.info("[%s] briefing text generated (used_llm=%s, chars=%d)", req.session_id, used_llm, len(text))

        audio_url = await _try_synthesize_and_publish(req.session_id, text)

        status = "ready"
    except Exception as exc:  # noqa: BLE001 - must always reach the callback below
        logger.exception("[%s] briefing generation failed unexpectedly: %s", req.session_id, exc)
        status = "failed"

    duration_seconds = round(time.monotonic() - started_at, 1)
    await _report_to_home_assistant(req.callback_url, req.session_id, status, text, audio_url, duration_seconds)


async def _try_synthesize_and_publish(session_id: str, text: str) -> Optional[str]:
    """Returns the /local/... URL Home Assistant can play, or None if TTS
    is disabled or fails — callers treat None as "text-only", not as an
    error (spec: TTS failure must not break the wake flow)."""
    if config.TTS_PROVIDER == "none":
        return None
    try:
        audio_bytes = await tts.synthesize(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] TTS synthesis failed, falling back to text-only: %s", session_id, exc)
        return None

    filename = f"{session_id}.mp3"
    (config.PUBLISH_DIR / filename).write_bytes(audio_bytes)
    # Home Assistant serves /config/www/* at /local/* automatically.
    # PUBLISH_DIR is bind-mounted to homeassistant/www/briefing/ in
    # compose.yaml, so this resolves to /local/briefing/<file>.mp3 there.
    return f"/local/briefing/{filename}"


async def _report_to_home_assistant(
    callback_url: str,
    session_id: str,
    status: str,
    text: str,
    audio_url: Optional[str],
    duration_seconds: float,
) -> None:
    payload = {
        "session_id": session_id,
        "status": status,
        "text": text,
        "audio_url": audio_url or "",
        "duration_seconds": duration_seconds,
    }
    try:
        async with httpx.AsyncClient(timeout=config.CALLBACK_TIMEOUT_SECONDS) as client:
            resp = await client.post(callback_url, json=payload)
            resp.raise_for_status()
        logger.info("[%s] reported %s to Home Assistant (%.1fs)", session_id, status, duration_seconds)
    except httpx.HTTPError as exc:
        # Nothing more we can do — HA will fall back to its deterministic
        # greeting since briefing_status never moves off "generating".
        logger.error("[%s] failed to reach Home Assistant callback: %s", session_id, exc)
