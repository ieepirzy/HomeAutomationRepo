"""Environment-driven configuration. No values are hardcoded here so the
service behaves identically across compose.yaml / Portainer stack env vars
/ local testing with a .env file."""

import os
from pathlib import Path


def _bool_env(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


BRIEFING_AUTH_TOKEN = os.environ["BRIEFING_AUTH_TOKEN"]

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

# One of: none | openai | elevenlabs
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "none").strip().lower()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # "Rachel" default

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
