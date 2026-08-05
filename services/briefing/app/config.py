"""Environment-driven configuration. No values are hardcoded here so the
service behaves identically across compose.yaml / Portainer stack env vars
/ local testing with a .env file."""

import os
from pathlib import Path

BRIEFING_AUTH_TOKEN = os.environ["BRIEFING_AUTH_TOKEN"]

# xAI (Grok) — chat completions API is OpenAI-compatible, so the `openai`
# SDK is pointed at xAI's base URL rather than pulling in a second SDK.
# TTS/STT are xAI-native REST endpoints with their own request shape (see
# tts.py) — not part of the OpenAI-compatible surface.
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
XAI_BASE_URL = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1")
# grok-4.3 is the deliberate default: full 1M context, meaningfully
# cheaper than grok-4.5 per xAI's published pricing, and this is a short
# daily generation task that doesn't need the flagship tier. Override to
# grok-4.5 for quality, or grok-4.1-fast / grok-build-0.1 for the cheapest
# options, via XAI_MODEL.
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4.3")

# xAI TTS. TTS_PROVIDER stays a switch (not hardcoded to "on") so
# TTS_PROVIDER=none still works as a zero-cost fallback that hands the
# raw briefing text to Home Assistant's own TTS engine instead — see
# tts.py and docs/wakeup-protocol.md "AI Morning Briefing / TTS".
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "xai").strip().lower()
XAI_TTS_VOICE_ID = os.environ.get("XAI_TTS_VOICE_ID", "eve")
XAI_TTS_LANGUAGE = os.environ.get("XAI_TTS_LANGUAGE", "en")

OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")
HOME_LAT = os.environ.get("HOME_LAT", "61.4991")
HOME_LON = os.environ.get("HOME_LON", "23.7871")

CACHE_DIR = Path(os.environ.get("CACHE_DIR", "/data/cache"))
PUBLISH_DIR = Path(os.environ.get("PUBLISH_DIR", "/data/published"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
PUBLISH_DIR.mkdir(parents=True, exist_ok=True)

# How long a callback POST to Home Assistant is allowed to take before we
# give up (the webhook itself is fast; this just guards against a wedged
# HA instance).
CALLBACK_TIMEOUT_SECONDS = 10
