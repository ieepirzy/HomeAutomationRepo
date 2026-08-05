# Briefing service

Generates the AI morning briefing (text + optional TTS audio) for the
wake-up protocol. Runs as its own container so Home Assistant's fast
path (lights + alarm) never has to wait on an LLM or TTS call — see
`docs/wakeup-protocol.md` "AI Morning Briefing" for the full design.

## Why a separate service at all

Home Assistant's `rest_command`/`tts.speak`/template actions can't do
three things this needs together: call an arbitrary LLM API with a
structured prompt, hold generated audio in a cache addressable by
session ID, and report back asynchronously without blocking the
automation that kicked it off. A small stateless HTTP service is the
straightforward way to get all three without a custom HA integration.

## Flow

1. Home Assistant `POST`s `/generate` with a session ID, a callback
   webhook URL, and whatever it already knows locally (current streak,
   today's priorities). Requires `Authorization: Bearer <BRIEFING_AUTH_TOKEN>`.
2. The endpoint returns `202 Accepted` immediately and does the actual
   work in a background task:
   - Weather (if `OPENWEATHER_API_KEY` is set) — omitted if unavailable,
     never invented.
   - Briefing text via the Claude API (`ANTHROPIC_API_KEY` /
     `ANTHROPIC_MODEL`) — falls back to a deterministic template built
     from the same facts if the API call fails, refuses, or returns
     empty text.
   - Audio, if `TTS_PROVIDER` is `openai` or `elevenlabs` — written to
     `PUBLISH_DIR` (bind-mounted into Home Assistant's `www/briefing/`,
     served at `/local/briefing/<file>.mp3`). If `TTS_PROVIDER=none` or
     synthesis fails, no audio is produced; Home Assistant speaks the
     returned text through its own configured TTS engine instead.
3. The background task `POST`s the result to the `callback_url` Home
   Assistant supplied — this is what fires the `ila_briefing_ready`
   webhook and unblocks playback.

Every stage is wrapped so a failure anywhere still produces a callback
(`status: "failed"` at worst) rather than leaving Home Assistant waiting
indefinitely.

## Configuration

All via environment variables — see `.env.example` at the repo root and
`compose.yaml`. Nothing is read from a config file inside the container.

| Variable | Required | Notes |
|---|---|---|
| `BRIEFING_AUTH_TOKEN` | yes | Shared secret checked on every `/generate` call |
| `ANTHROPIC_API_KEY` | yes | Briefing text generation |
| `ANTHROPIC_MODEL` | no | Default `claude-opus-5` |
| `TTS_PROVIDER` | no | `none` (default) / `openai` / `elevenlabs` |
| `OPENAI_API_KEY` | if `TTS_PROVIDER=openai` | |
| `ELEVENLABS_API_KEY` | if `TTS_PROVIDER=elevenlabs` | |
| `ELEVENLABS_VOICE_ID` | no | Default is ElevenLabs' "Rachel" voice |
| `OPENWEATHER_API_KEY` | no | Omit weather section if unset |
| `HOME_LAT` / `HOME_LON` | no | Defaults to Tampere, FI |
| `CACHE_DIR` / `PUBLISH_DIR` | no | Set by compose.yaml; shouldn't need overriding |

## Endpoints

- `GET /healthz` — used by the Docker healthcheck.
- `POST /generate` — see above. Body: `{session_id, callback_url,
  test_mode, current_streak, priorities, name}`.

## Local testing without Home Assistant

```sh
cd services/briefing
pip install -r requirements.txt
BRIEFING_AUTH_TOKEN=test ANTHROPIC_API_KEY=sk-ant-... \
  CACHE_DIR=/tmp/cache PUBLISH_DIR=/tmp/published \
  uvicorn app.main:app --port 8420 --reload

curl -X POST http://localhost:8420/generate \
  -H "Authorization: Bearer test" -H "Content-Type: application/json" \
  -d '{"session_id": "test-1", "callback_url": "http://localhost:9999/echo",
       "current_streak": 8, "priorities": ["Finish the Mirarun dashboard handoff"]}'
```

Run a throwaway listener (`nc -l 9999` or similar) on the callback URL to
see the reported payload.
