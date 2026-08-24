# Device integrations

This deployment keeps device integrations that need discovery or interactive
pairing in Home Assistant's UI-managed config entries. Their state is written
to `/config/.storage`, which `compose.yaml` persists from
`data/homeassistant/storage` outside the Git working tree.

Do not add device IDs, local keys, or cloud credentials to tracked YAML or Git.
WiZ, LocalTuya, and Xiaomi Miot config entries are created through the Home
Assistant UI and persist in the separately mounted `/config/.storage`.

## WiZ

WiZ control is local: Home Assistant communicates directly with each device on
the LAN. The `homeassistant` container already uses host networking so discovery
and local device traffic can reach the apartment network.

1. Add each light or socket to the apartment Wi-Fi with the WiZ mobile app.
2. In the WiZ app, open **Settings → Security settings** and confirm **Allow
   local communication** is enabled.
3. In Home Assistant, open **Settings → Devices & services**.
4. If WiZ appears under **Discovered**, select **Configure**. Otherwise select
   **Add integration**, search for **WiZ**, and follow the prompt. For manual
   setup, use the device's LAN IP address.
5. Assign the resulting devices to areas and give their entities stable,
   descriptive names before referencing them from tracked automations.

If discovery fails, first confirm that Home Assistant and the device can reach
each other on the LAN and that client/AP isolation is disabled. A DHCP
reservation is useful if a device was added manually by IP.

## LocalTuya

This deployment uses the community-maintained
[`xZetsubou/hass-localtuya`](https://github.com/xZetsubou/hass-localtuya)
fork, not Home Assistant's official cloud-backed Tuya integration. Compose
builds a checksum-pinned installer image and runs it before Home Assistant. The
installer places the custom component in the runtime-only
`data/homeassistant/custom_components` bind mount, so a Portainer redeploy can
recreate it without HACS or untracked files in `homeassistant/`.

### Provisioning

1. Deploy the updated stack. In the Portainer logs, confirm the one-shot
   `localtuya-installer` container exits successfully after reporting the
   installed version.
2. Restart Home Assistant if this is the first deployment, then open **Settings
   → Devices & services → Add integration** and select **Local Tuya**.
3. For cloud-free operation, leave LocalTuya's optional Cloud API setup
   disabled and add devices manually. Each device requires its **Device ID**,
   **local key**, LAN IP address, and protocol version.
4. Close the Smart Life/Tuya Smart app while configuring devices. Some devices
   accept only one local connection at a time.
5. Select the discovered device, supply its ID and local key, and configure its
   entities and DP IDs. Automatic entity configuration requires LocalTuya's
   optional cloud API; manual DP configuration does not.
6. Assign the resulting devices to areas and give their entities stable,
   descriptive names before referencing them from tracked automations.

LocalTuya controls configured devices on the LAN after setup, but it cannot
derive a device's local key from local discovery alone. Commissioning a stock
Tuya device and obtaining its ID/local key may still require the Tuya app and a
temporary Tuya developer-cloud workflow (for example through TinyTuya). Record
the keys in a password manager before removing the app or cloud project. Do not
commit them to this repository.

Only block a device's internet access after local control and state updates have
been tested through a power cycle. LocalTuya being local does not guarantee that
every vendor firmware remains fully functional without internet access.

## Xiaomi Miot

This deployment installs the community-maintained
[`al-one/hass-xiaomi-miot`](https://github.com/al-one/hass-xiaomi-miot)
integration from a checksum-pinned release before Home Assistant starts. The
custom component is reproducible from Git, while each device's local token stays
inside HA's persistent `/config/.storage` rather than tracked configuration.

For the Xiaomi Smart Humidifier 2 EU (`deerma.humidifier.jsq2w`):

1. Pair the humidifier in Xiaomi Home long enough to provision Wi-Fi, then give
   it a DHCP reservation.
2. Deploy this stack and confirm the `xiaomi-miot-installer` one-shot container
   reports version `1.1.4` and exits successfully.
3. Obtain the 32-character local token inside HA: temporarily add **Xiaomi Miot
   → Add devices using Mi Account**, then call the
   `xiaomi_miot.get_token` action from **Developer tools → Actions** with the
   humidifier name, IP, or model as `name`. Copy the token from the action
   response directly into a password manager. Remove the temporary account-based
   Xiaomi Miot entry afterward; do not paste the token into logs, chat, or Git.
4. Add **Xiaomi Miot** again and select **Add device using host/token (LAN
   integration)**. Enter the reserved
   LAN IP and local token. Let the integration detect the model; if manual input
   is required, use `deerma.humidifier.jsq2w`.
5. The final entry must not contain a Xiaomi account or use Cloud mode. If
   connection mode is offered, select **Local**.
6. Verify power, preset/mode, target humidity, current humidity, temperature,
   water state, and recovery after both an HA restart and a humidifier power
   cycle.

The integration can fetch public MIoT schema metadata, but device state and
commands use the LAN host/token path. Only deny the humidifier internet access
after the restart and power-cycle checks pass. Keep DHCP and local HA-to-device
traffic available; miIO commonly uses UDP port 54321. If the device needs time,
provide a local NTP service rather than restoring general WAN access.

## Verification and persistence

For each integration:

1. Toggle one non-critical device from Home Assistant and confirm the physical
   state and UI state agree.
2. Restart only the `homeassistant` container and confirm the integration and
   entities return without re-pairing.
3. After the next Portainer pull-and-redeploy, confirm the same again. If the
   integration disappears, verify that the host's populated
   `data/homeassistant/storage` and `data/homeassistant/custom_components`
   directories are still mounted at `/config/.storage` and
   `/config/custom_components`; do not attempt to reconstruct their files in
   Git.

References: [WiZ integration](https://www.home-assistant.io/integrations/wiz/),
[LocalTuya documentation](https://xzetsubou.github.io/hass-localtuya/), and
[Xiaomi Miot](https://github.com/al-one/hass-xiaomi-miot).

## Personal information integrations

These integrations are UI-managed for the same reason as device integrations:
their Apple/Google credentials must remain in Home Assistant's private
`.storage`, not tracked YAML or Portainer environment variables.

### iCloud Calendar through CalDAV

1. Generate an Apple app-specific password.
2. In **Settings -> Devices & services**, add **CalDAV**.
3. Use `https://caldav.icloud.com/`, the Apple ID, and the app-specific
   password.
4. Select only the calendars Mira needs and add their resulting `calendar.*`
   entity IDs to `HA_CALENDAR_ENTITIES` in the Portainer stack.
5. Confirm upcoming events appear in Developer Tools before relying on the
   bedtime or morning briefing.

CalDAV is polled on approximately a 15-minute cadence. Keep calendar mutation
out of the v1 read-only MCP boundary. A future `create_calendar_event()` tool
will write through iCloud CalDAV using a separate credential and a single
allowlisted destination calendar, preferably a dedicated **Mira Inbox** for
events inferred from mail.

### Read-only email

Add one **IMAP** integration entry per provider:

- Gmail uses `imap.gmail.com` on port `993`, SSL, and a Google app password.
- iCloud Mail uses `imap.mail.me.com` on port `993`, SSL, the iCloud username
  (or full address if required), and an Apple app-specific password.

The agent-facing read path is general: it may search/list mailbox metadata and
fetch any individual email by stable ID. It is not limited to bills, events, or
preselected senders. Keep mailbox actions such as delete, move or mark-seen
outside the read-only agent surface even though HA's IMAP integration supports
them.

No incoming email starts Mira in v1. HA's `imap_content` events are merely a
possible source for a later trigger/subscription design; do not connect them to
the agent runner yet. This does not limit what Mira can retrieve through an
explicit read tool call during an already-running turn.

Do not forward arbitrary email bodies into an agent prompt. Messages are
untrusted input and may contain prompt injection; body retrieval should be an
explicit follow-up operation after source and policy checks.

Outbound Gmail and iCloud Mail are planned, not enabled. Gmail can use the
**Google Mail** OAuth integration. iCloud can use **SMTP** with
`smtp.mail.me.com:587`, STARTTLS and an Apple app-specific password. Future
`draft_email()` and `send_email()` tools remain separate from inbound read
access; sending receives the stricter authority.

Official references: [CalDAV](https://www.home-assistant.io/integrations/caldav/),
[Google Mail](https://www.home-assistant.io/integrations/google_mail/), and
[IMAP](https://www.home-assistant.io/integrations/imap/),
[SMTP](https://www.home-assistant.io/integrations/smtp/), and
[Apple's iCloud Mail server settings](https://support.apple.com/en-ie/102525).
