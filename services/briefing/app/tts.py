"""Pluggable text-to-speech. TTS_PROVIDER selects the backend:

  none        - no audio is generated; the caller (main.py) reports the
                text only and Home Assistant falls back to its own
                native TTS engine to speak it (see
                docs/wakeup-protocol.md "AI Morning Briefing").
  openai      - OpenAI's /v1/audio/speech endpoint.
  elevenlabs  - ElevenLabs' text-to-speech endpoint.

Every provider function returns raw audio bytes (mp3) or raises — callers
must catch and treat as a TTS failure per spec section 14 ("If TTS
fails: Complete the wake flow anyway... Log the failure."). This module
never decides fallback behavior itself, it only generates audio.
"""

import logging

import httpx

from . import config

logger = logging.getLogger("briefing.tts")


class TTSError(Exception):
    pass


async def synthesize(text: str) -> bytes:
    if config.TTS_PROVIDER == "openai":
        return await _synthesize_openai(text)
    if config.TTS_PROVIDER == "elevenlabs":
        return await _synthesize_elevenlabs(text)
    raise TTSError(f"unknown or unset TTS_PROVIDER: {config.TTS_PROVIDER!r}")


async def _synthesize_openai(text: str) -> bytes:
    if not config.OPENAI_API_KEY:
        raise TTSError("TTS_PROVIDER=openai but OPENAI_API_KEY is not set")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
            json={
                "model": "gpt-4o-mini-tts",
                "voice": "alloy",
                "input": text,
                "response_format": "mp3",
            },
        )
        resp.raise_for_status()
        return resp.content


async def _synthesize_elevenlabs(text: str) -> bytes:
    if not config.ELEVENLABS_API_KEY:
        raise TTSError("TTS_PROVIDER=elevenlabs but ELEVENLABS_API_KEY is not set")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}",
            headers={
                "xi-api-key": config.ELEVENLABS_API_KEY,
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
        )
        resp.raise_for_status()
        return resp.content
