"""Text-to-speech via xAI's native TTS API.

TTS_PROVIDER stays a switch even though "xai" is the only real backend:
TTS_PROVIDER=none is a legitimate, zero-cost configuration where no audio
is generated at all and Home Assistant speaks the returned briefing text
through its own configured TTS engine instead — see main.py and
docs/wakeup-protocol.md "AI Morning Briefing / TTS".

Raises TTSError on any failure; callers must catch it and treat as a TTS
failure per spec section 14 ("If TTS fails: Complete the wake flow
anyway... Log the failure.") — this module never decides fallback
behavior itself, it only generates audio.
"""

import logging

import httpx

from . import config

logger = logging.getLogger("briefing.tts")


class TTSError(Exception):
    pass


async def synthesize(text: str) -> bytes:
    if config.TTS_PROVIDER != "xai":
        raise TTSError(f"unknown or unset TTS_PROVIDER: {config.TTS_PROVIDER!r}")
    return await _synthesize_xai(text)


async def _synthesize_xai(text: str) -> bytes:
    if not config.XAI_API_KEY:
        raise TTSError("TTS_PROVIDER=xai but XAI_API_KEY is not set")

    # xAI's TTS endpoint caps input at 15,000 characters; the briefing is
    # always well under that (SYSTEM_PROMPT caps it at ~70 words), but
    # truncate defensively rather than let an oversized request 400.
    truncated = text[:15000]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{config.XAI_BASE_URL.rstrip('/')}/tts",
            headers={
                "Authorization": f"Bearer {config.XAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "text": truncated,
                "voice_id": config.XAI_TTS_VOICE_ID,
                "language": config.XAI_TTS_LANGUAGE,
            },
        )
        resp.raise_for_status()
        # Without with_timestamps (not requested here), the response body
        # is raw audio bytes directly — no JSON envelope to unwrap.
        return resp.content
