"""Environment-driven configuration — see .env.example and compose.yaml."""

import os

# Path-segment tokens act as bearer secrets for the two GET endpoints,
# same convention as Home Assistant's own webhook_id — generate real
# random values (openssl rand -hex 24), never reuse the placeholders in
# .env.example.
WAKE_TOKEN = os.environ["WAKE_TOKEN"]
UNDOCK_TOKEN = os.environ["UNDOCK_TOKEN"]

# Home Assistant's REST API — this gateway runs on network_mode: host
# (see compose.yaml) specifically so 127.0.0.1 reaches the HA container
# directly, the same way the briefing service reaches Home Assistant's
# loopback-bound port from the other direction.
HA_BASE_URL = os.environ.get("HA_BASE_URL", "http://127.0.0.1:8123")
# Long-lived access token, generated once via the Home Assistant UI
# (Profile > Security > Long-Lived Access Tokens) — see
# docs/wakeup-protocol.md "Wake gateway" for the setup step. Not
# something this repo can provision declaratively.
HA_LONG_LIVED_TOKEN = os.environ["HA_LONG_LIVED_TOKEN"]

HA_REQUEST_TIMEOUT_SECONDS = 10
