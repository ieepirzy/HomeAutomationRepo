# Wake gateway

Standalone Python webhook server that iOS Shortcuts talks to directly —
the adapter boundary for wake detection and the Shortcut-triggered undock
fallback (spec section 8). See `docs/wakeup-protocol.md` "Wake gateway"
for why this is a separate service rather than using Home Assistant's own
built-in webhook automation trigger (which could equally have done this
job), and section 3/5 for the full Apple-side design and limitations.

## Why this exists

Without *some* server-reachable signal, "the user woke up" and "the
phone left the charger" can only be observed from a native watchOS/iOS
app polling sensors continuously — well outside this project's scope.
The realistic alternative is an iOS Shortcuts Personal Automation that
fires on a Sleep Focus transition / charger-state change and hits an
HTTP endpoint. This service is that endpoint: two `GET` routes simple
enough that the corresponding Shortcut is a single "Get Contents of URL"
action, no headers or request body to configure.

## Endpoints

| Route | Effect |
|---|---|
| `GET /wake/<WAKE_TOKEN>` | Fires `ila_wake_detected` (`source: apple_watch`) on Home Assistant's event bus |
| `GET /undock/<UNDOCK_TOKEN>` | Fires `ila_phone_undocked` (`source: shortcut`) — the fallback path; the primary undock signal is still the Companion App's battery-state sensor, see `docs/wakeup-protocol.md` §5 |
| `GET /healthz` | Docker healthcheck |

The token is a path segment, not a header or query param, purely so the
Shortcut is a single action with a fixed URL and nothing else to
configure. It's the entire auth mechanism for these routes — generate
real random values (`openssl rand -hex 24`), never the placeholders in
`.env.example`.

## How it reaches Home Assistant

`POST {HA_BASE_URL}/api/events/<event_type>` — Home Assistant's
documented [REST API for firing bus events](https://developers.home-assistant.io/docs/api/rest/#post-apieventsevent_type),
authenticated with a Long-Lived Access Token. This is the same event bus
`homeassistant/packages/wakeup_protocol.yaml`'s `trigger: event`
automations already consume — nothing downstream of Home Assistant's
event bus knows or cares that this gateway exists instead of HA's own
webhook trigger.

**One-time setup (cannot be done from this repo):** in the Home
Assistant UI, go to your profile → Security → Long-Lived Access Tokens →
Create Token, and put the value in `HA_LONG_LIVED_TOKEN`.

## Configuration

| Variable | Required | Notes |
|---|---|---|
| `WAKE_TOKEN` | yes | Path-segment secret for `/wake/<token>` |
| `UNDOCK_TOKEN` | yes | Path-segment secret for `/undock/<token>` |
| `HA_LONG_LIVED_TOKEN` | yes | From the Home Assistant UI, see above |
| `HA_BASE_URL` | no | Default `http://127.0.0.1:8123` — works because this service runs on `network_mode: host`, same as Home Assistant itself (see compose.yaml) |

## iOS Shortcuts setup

1. Shortcuts → Automation → New Personal Automation → the trigger from
   `docs/wakeup-protocol.md` §3 (Sleep Focus ending, within the wake
   window).
2. Action: "Get Contents of URL", method `GET`,
   `http://<home-assistant-host>:8422/wake/<WAKE_TOKEN>`.
3. Turn off "Ask Before Running".
4. Repeat for the undock fallback if you want it in addition to the
   Companion App battery-state sensor (`docs/wakeup-protocol.md` §5) —
   trigger on a MagSafe/Qi accessory disconnect, URL `.../undock/<UNDOCK_TOKEN>`.

If Home Assistant is only reachable on the home network, put it behind a
VPN (WireGuard) rather than forwarding the gateway's port directly to the
internet — same recommendation as for the alarm webhook.

## Local testing

```sh
cd services/wake-gateway
pip install -r requirements.txt
WAKE_TOKEN=test-wake UNDOCK_TOKEN=test-undock \
  HA_BASE_URL=http://localhost:8123 HA_LONG_LIVED_TOKEN=eyJ... \
  uvicorn app.main:app --port 8422 --reload

curl http://localhost:8422/wake/test-wake
```
