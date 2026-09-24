import os

# app.server builds its Config from the environment at import time. Provide
# the three required values so calendar tests can import and patch it.
os.environ.setdefault("MIRA_HOME_MCP_TOKEN", "test-mcp-token")
os.environ.setdefault("HA_LONG_LIVED_TOKEN", "test-ha-token")
os.environ.setdefault("HA_LOCATION_ENTITY", "device_tracker.test_phone")
