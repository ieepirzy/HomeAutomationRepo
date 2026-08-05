# Briefing service

Generates the AI morning briefing (text + optional TTS audio) for the
wake-up protocol. Runs as its own container so Home Assistant's fast
path (lights + alarm) never has to wait on an LLM or TTS call — see
`docs/wakeup-protocol.md` "AI Morning Briefing" for the full design.

Uses **xAI** (Grok) for both text generation and text-to-speech — chosen
for pricing on the LLM side and native TTS quality-per-euro, per
household preference (see `docs/wakeup-protocol.md` for the tradeoff
notes). Chat completions go through xAI's OpenAI-compatible endpoint via
the `openai` SDK with a `base_url` override; TTS uses xAI's own
non-OpenAI-compatible REST endpoint directly.

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
   - Briefing text via xAI's Grok (`XAI_API_KEY` / `XAI_MODEL`, default
     `grok-4.3`) — falls back to a deterministic template built from the
     same facts if the API call fails, is refused (`finish_reason ==
     "content_filter"`), or returns empty text.
   - Audio, if `TTS_PROVIDER=xai` (the default) — written to
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
| `XAI_API_KEY` | yes | Briefing text generation and TTS |
| `XAI_MODEL` | no | Default `grok-4.3` — cheaper, full 1M context. `grok-4.5` for quality, `grok-4.1-fast` / `grok-build-0.1` for cheapest/lowest-latency |
| `XAI_BASE_URL` | no | Default `https://api.x.ai/v1` |
| `TTS_PROVIDER` | no | `xai` (default) / `none` |
| `XAI_TTS_VOICE_ID` | no | Default `eve`. List others via `GET https://api.x.ai/v1/tts/voices` |
| `XAI_TTS_LANGUAGE` | no | BCP-47 code, default `en` |
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
BRIEFING_AUTH_TOKEN=test XAI_API_KEY=xai-... \
  CACHE_DIR=/tmp/cache PUBLISH_DIR=/tmp/published \
  uvicorn app.main:app --port 8420 --reload

curl -X POST http://localhost:8420/generate \
  -H "Authorization: Bearer test" -H "Content-Type: application/json" \
  -d '{"session_id": "test-1", "callback_url": "http://localhost:9999/echo",
       "current_streak": 8, "priorities": ["Finish the Mirarun dashboard handoff"]}'
```

Run a throwaway listener (`nc -l 9999` or similar) on the callback URL to
see the reported payload.
