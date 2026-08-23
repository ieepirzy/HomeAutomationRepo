from app.config import Config


BASE_ENV = {
    "MIRA_HOME_MCP_TOKEN": "mcp-secret",
    "HA_LONG_LIVED_TOKEN": "ha-secret",
    "HA_LOCATION_ENTITY": "device_tracker.phone",
}


def test_home_state_groups_are_explicit_and_semantic():
    config = Config.from_env(
        {
            **BASE_ENV,
            "HA_OCCUPANCY_ENTITIES": "person.ila,binary_sensor.home_occupied",
            "HA_ENTRY_ENTITIES": "binary_sensor.kitchen_window",
            "HA_WEATHER_ENTITIES": "weather.forecast_home",
            "HA_DESKTOP_ACTIVITY_ENTITIES": "sensor.desktop_activity",
            "HA_MODE_ENTITIES": "input_boolean.sleep_mode,input_boolean.wake_mode",
        }
    )

    assert config.home_state_groups["occupancy"] == (
        "person.ila",
        "binary_sensor.home_occupied",
    )
    assert config.home_state_groups["entries"] == ("binary_sensor.kitchen_window",)
    assert config.home_state_groups["weather"] == ("weather.forecast_home",)
    assert config.home_state_groups["desktop_activity"] == ("sensor.desktop_activity",)
    assert config.home_state_groups["modes"] == (
        "input_boolean.sleep_mode",
        "input_boolean.wake_mode",
    )


def test_paused_prototype_state_allowlist_remains_compatible():
    config = Config.from_env(
        {**BASE_ENV, "HA_STATE_ENTITIES": "sensor.legacy_one,sensor.legacy_two"}
    )

    assert config.home_state_groups["other"] == (
        "sensor.legacy_one",
        "sensor.legacy_two",
    )


def test_gmail_and_icloud_are_independent_optional_accounts():
    config = Config.from_env(
        {
            **BASE_ENV,
            "GMAIL_IMAP_USERNAME": "ila@gmail.example",
            "GMAIL_IMAP_PASSWORD": "gmail-app-password",
            "GMAIL_IMAP_FOLDERS": "INBOX,[Gmail]/All Mail",
            "ICLOUD_IMAP_USERNAME": "ila@icloud.example",
            "ICLOUD_IMAP_PASSWORD": "icloud-app-password",
            "ICLOUD_IMAP_FOLDERS": "INBOX,Archive",
        }
    )

    assert [(item.name, item.host, item.folders) for item in config.email_accounts] == [
        ("gmail", "imap.gmail.com", ("INBOX", "[Gmail]/All Mail")),
        ("icloud", "imap.mail.me.com", ("INBOX", "Archive")),
    ]


def test_partial_email_credentials_fail_closed():
    try:
        Config.from_env({**BASE_ENV, "GMAIL_IMAP_USERNAME": "ila@gmail.example"})
    except RuntimeError as exc:
        assert "must be set together" in str(exc)
    else:
        raise AssertionError("partial IMAP credentials were accepted")
