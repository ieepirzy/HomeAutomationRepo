"""Environment-driven configuration for the Mira Home MCP adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _csv(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in (value or "").split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class EmailAccountConfig:
    """One explicitly configured read-only IMAP account."""

    name: str
    provider: str
    host: str
    username: str
    password: str
    folders: tuple[str, ...] = ("INBOX",)
    port: int = 993


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration. Secrets are injected by Portainer, never git."""

    mcp_token: str
    ha_token: str
    location_entity: str
    ha_base_url: str = "http://127.0.0.1:8123"
    address_entity: str | None = None
    activity_entity: str | None = None
    calendar_entities: tuple[str, ...] = ()
    occupancy_entities: tuple[str, ...] = ()
    entry_entities: tuple[str, ...] = ()
    light_entities: tuple[str, ...] = ()
    climate_entities: tuple[str, ...] = ()
    humidity_entities: tuple[str, ...] = ()
    weather_entities: tuple[str, ...] = ()
    media_entities: tuple[str, ...] = ()
    desktop_activity_entities: tuple[str, ...] = ()
    mode_entities: tuple[str, ...] = ()
    extra_state_entities: tuple[str, ...] = ()
    email_accounts: tuple[EmailAccountConfig, ...] = ()
    email_max_body_bytes: int = 524_288
    email_max_body_chars: int = 20_000
    request_timeout_seconds: float = 10.0

    @property
    def home_state_groups(self) -> dict[str, tuple[str, ...]]:
        """Return the operator-defined semantic groups exposed by the MCP."""
        return {
            "occupancy": self.occupancy_entities,
            "entries": self.entry_entities,
            "lights": self.light_entities,
            "climate": self.climate_entities,
            "humidity": self.humidity_entities,
            "weather": self.weather_entities,
            "media": self.media_entities,
            "desktop_activity": self.desktop_activity_entities,
            "modes": self.mode_entities,
            "other": self.extra_state_entities,
        }

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "Config":
        env = environ if environ is not None else dict(os.environ)
        required = ("MIRA_HOME_MCP_TOKEN", "HA_LONG_LIVED_TOKEN", "HA_LOCATION_ENTITY")
        missing = [key for key in required if not env.get(key)]
        if missing:
            raise RuntimeError(f"missing required Mira Home configuration: {', '.join(missing)}")

        email_accounts = []
        for prefix, name, provider, host in (
            ("GMAIL", "gmail", "gmail", "imap.gmail.com"),
            ("ICLOUD", "icloud", "icloud", "imap.mail.me.com"),
        ):
            username = env.get(f"{prefix}_IMAP_USERNAME", "").strip()
            password = env.get(f"{prefix}_IMAP_PASSWORD", "")
            if bool(username) != bool(password):
                raise RuntimeError(
                    f"{prefix}_IMAP_USERNAME and {prefix}_IMAP_PASSWORD must be set together"
                )
            if username:
                folders = _csv(env.get(f"{prefix}_IMAP_FOLDERS")) or ("INBOX",)
                email_accounts.append(
                    EmailAccountConfig(
                        name=name,
                        provider=provider,
                        host=env.get(f"{prefix}_IMAP_HOST", host),
                        port=int(env.get(f"{prefix}_IMAP_PORT", "993")),
                        username=username,
                        password=password,
                        folders=folders,
                    )
                )

        email_max_body_bytes = int(env.get("EMAIL_MAX_BODY_BYTES", "524288"))
        email_max_body_chars = int(env.get("EMAIL_MAX_BODY_CHARS", "20000"))
        if email_max_body_bytes < 1 or email_max_body_chars < 1:
            raise RuntimeError("EMAIL_MAX_BODY_BYTES and EMAIL_MAX_BODY_CHARS must be positive")

        return cls(
            mcp_token=env["MIRA_HOME_MCP_TOKEN"],
            ha_token=env["HA_LONG_LIVED_TOKEN"],
            location_entity=env["HA_LOCATION_ENTITY"],
            ha_base_url=env.get("HA_BASE_URL", "http://127.0.0.1:8123").rstrip("/"),
            address_entity=env.get("HA_ADDRESS_ENTITY") or None,
            activity_entity=env.get("HA_ACTIVITY_ENTITY") or None,
            calendar_entities=_csv(env.get("HA_CALENDAR_ENTITIES")),
            occupancy_entities=_csv(env.get("HA_OCCUPANCY_ENTITIES")),
            entry_entities=_csv(env.get("HA_ENTRY_ENTITIES")),
            light_entities=_csv(env.get("HA_LIGHT_ENTITIES")),
            climate_entities=_csv(env.get("HA_CLIMATE_ENTITIES")),
            humidity_entities=_csv(env.get("HA_HUMIDITY_ENTITIES")),
            weather_entities=_csv(env.get("HA_WEATHER_ENTITIES")),
            media_entities=_csv(env.get("HA_MEDIA_ENTITIES")),
            desktop_activity_entities=_csv(env.get("HA_DESKTOP_ACTIVITY_ENTITIES")),
            mode_entities=_csv(env.get("HA_MODE_ENTITIES")),
            # HA_STATE_ENTITIES was used by the paused prototype. Keep it as an
            # alias so a pre-existing Portainer value is not silently ignored.
            extra_state_entities=_csv(
                env.get("HA_EXTRA_STATE_ENTITIES") or env.get("HA_STATE_ENTITIES")
            ),
            email_accounts=tuple(email_accounts),
            email_max_body_bytes=email_max_body_bytes,
            email_max_body_chars=email_max_body_chars,
            request_timeout_seconds=float(env.get("HA_REQUEST_TIMEOUT_SECONDS", "10")),
        )
