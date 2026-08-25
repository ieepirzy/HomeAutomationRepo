# Integration shortlist

This is a living shortlist of Home Assistant integrations worth evaluating for
the apartment. Inclusion here is not authorization to install an integration,
grant credentials, expose it to Mira, or enable write actions. UI-managed
credentials stay in Home Assistant's persisted `.storage` and out of Git.

## Rollout status

- Live: ASUSWRT (router and selected known-client devices discovered), Pi-hole
  v6 (legacy host installation at `192.168.50.38`, integrated through a
  dedicated app password), Steam, Epic Games Store, Syncthing (central
  WireGuard hub at `http://10.8.0.1:8384`), WAQI (Hannikaisenkatu measuring
  station), Holiday (Finland), Workday (Finland), iCloud CalDAV (`Työ` and
  `Koti`), Sisu university calendar (direct Remote Calendar subscription),
  System Bridge (Arch desktop and Linux Mint laptop), OpenRGB (Arch desktop;
  headless user service)
- In progress: HomeKit Bridge (integration created; entity filtering and Apple
  Home pairing remain)
- Next: restrict the OpenRGB SDK port to Home Assistant, then evaluate the
  remaining infrastructure integrations
- Deferred: Spotify, because Spotify's Development Mode Web API now requires
  Premium and obtaining Premium solely for HA is not worthwhile; Jellyfin,
  pending a separate media-stack migration design and storage/network audit
- Maintenance backlog: update the existing Pi-hole Core, Web, and FTL
  installation separately from HA integration work after backing up its
  configuration and confirming a rollback path; reset the central Syncthing
  GUI credentials and verify folder versioning independently of HA monitoring

## High-value next

| Integration | Intended value | Boundary or prerequisite |
| --- | --- | --- |
| ASUSWRT | Router telemetry and a Wi-Fi association signal for confirmed arrival/occupancy (live) | HTTPS on LAN; never Telnet or WAN administration. Expose only derived presence to Mira. |
| HomeKit Bridge | Curated HA devices and scenes in Apple Home/Siri (integration created; pairing pending) | Include-list only; do not expose diagnostics, raw wake buttons, or Mira internals. |
| Jellyfin | Playback context, media browsing, and suppression of low-priority speech during playback (deferred) | Treat moving the media/arr stack to the desktop as a separate migration. Audit the real network path before assuming the homelab can remain a mounted storage backend. |
| Pi-hole | Local DNS-blocking health, statistics, and temporary-disable action (live) | Uses a dedicated Pi-hole v6 app password. Do not grant Mira the disable action by default. |
| Spotify | Playback context and explicit media control (deferred) | Spotify Premium and a developer application are now mandatory; do not subscribe solely for this integration. |
| Steam | Online/now-playing state and game artwork (live) | Uses a Steam Web API key; useful as activity context, not occupancy proof by itself. |
| Epic Games Store | Calendar of current and upcoming free games and discounts (live) | Cloud-polled convenience integration; no account credential is required by the documented setup. |
| Syncthing | Per-folder synchronization health for the laptop/desktop knowledge stores (live) | Uses the central hub's local API key over WireGuard; monitoring only. GUI credential recovery and versioning verification remain maintenance work. |
| WAQI | Outdoor AQI context for ventilation and briefings (live; Hannikaisenkatu station) | Cloud API token; compare the outdoor station with a future local indoor sensor. |

## Developer and agent infrastructure

| Integration | Intended value | Boundary or prerequisite |
| --- | --- | --- |
| Portainer | Container, stack, endpoint, resource, and health visibility | The integration currently requires an administrator access token and exposes destructive controls. Start read-only at the agent boundary; do not expose stop, restart, recreate, or prune tools to Mira. |
| MQTT | Projection bus for OBD2, MiraRun attention state, DIY sensors, and desktop daemons | Broker runs as a separate container. Use retained state and availability deliberately; do not route every API through MQTT. |
| ESPHome | Future local contact, air-quality, Bluetooth-proxy, and occupancy hardware | ESPHome dashboard/build service is separate from HA Container. |
| MCP Server | Compare HA's generic exposed-entity MCP surface with `mira-home-mcp` | Keep the custom semantic tools and narrow authority as the default; test with a dedicated HA identity and exposure allowlist. |
| FFmpeg | Audio/video stream plumbing for future cameras, microphones, media extraction, and noise/motion sensors | Already present in the official HA Container image; the homelab is not suitable for heavy transcoding. |
| Feedreader | Low-volume RSS/Atom event source | New entries enter HA as untrusted external content. Do not trigger Mira on arbitrary feeds without filtering and deduplication. |
| Cloudflare | Dynamic public IPv4 A-record updates | Not Cloudflare Tunnel, DNS analytics, or general Cloudflare management. Needs DNS-edit permission and is unnecessary if WireGuard is the only remote path. |
| GitHub | Lightweight personal-project repository state | Prefer a MiraRun-derived attention count for workflow meaning; do not duplicate company production observability. |

## Situational or curiosity

| Integration | What it actually does | Assessment |
| --- | --- | --- |
| Coinbase | Read account balances and exchange rates | Interesting, but only with a view-only API key. Keep finance entities out of Mira's general home-state response. |
| Discord | Sends outbound bot notifications, files, and embeds | Vesktop is irrelevant; the integration cannot consume incoming Discord messages. Defer unless a dedicated HA notification channel becomes useful. |
| GeoJSON | Converts an arbitrary GeoJSON event feed into distance-filtered map entities | Useful building block only after choosing a relevant Finnish/local feed. |
| GeoNet NZ Quakes/Volcano | New Zealand geological-event feeds | Interesting but geographically irrelevant in Finland. |
| GDACS | Distance-filtered worldwide disaster alerts | Potentially useful for travel/global-awareness context; avoid noisy spoken alerts. |
| Holiday / Workday | Region-specific public-holiday calendar and workday state (live; Finland) | Useful for Finland-aware morning routines and workday logic. |
| Home Assistant Analytics Insights | Sensors containing public HA integration-usage statistics | Fun ecosystem telemetry, no apartment automation value. |
| ISS | International Space Station visibility/location information | Harmless dashboard novelty. |
| Nmap Tracker | Active LAN scans for device presence | Redundant and noisier once ASUSWRT tracking is available; avoid frequent scans. |
| Speedtest.net | Ping, download, and upload tests | Disable hourly polling; run manually or at a low cadence to avoid consuming the connection and CPU for vanity telemetry. |
| Ruuvi | Local Bluetooth environmental tags | Strong future hardware candidate based on prior positive experience. |
| Sentry/Uptime Kuma | Service-health and incident state | Keep personal-service summaries only; do not mirror company production telemetry into HA. |
| Chess.com | Chess account/game sensors | No current use. |

## Names that are easy to misread

- **Mobile App** is the server-side integration used by the Companion apps. It
  already backs the iPhone and iPad registrations, sensors, location, and
  notification actions.
- **Home Assistant iOS** is documentation/legacy naming around the Apple
  Companion app, not a second integration to add alongside Mobile App.
- There is no single generic **Google** integration. Google Assistant exposes HA
  devices to Assistant; Google Assistant SDK sends commands to Google; Calendar,
  Cast, Gemini, Mail, Maps, Tasks, and other Google services are separate.
- **FFmpeg** is infrastructure used by other integrations, not a media library
  or a solution to Jellyfin's transcoding-resource problem.

## Finnish transit opportunity

There is no native VR or Linkki integration in core. Finland nevertheless has
better source data than many of the one-off transit integrations:

- Fintraffic Digitraffic publishes passenger-train static GTFS, GTFS-Realtime
  positions and updates, REST/Swagger, and GraphQL data for timetables, delays,
  train positions, and consists.
- Jyväskylä Linkki publishes open transit data through the Finnish/Waltti
  ecosystem.
- HA's legacy GTFS integration can read a static GTFS archive and expose the
  next scheduled departure, but it does not consume GTFS-Realtime. A small
  local adapter or purpose-built integration would be preferable for useful
  live VR/Linkki departures and delay alerts.

Possible later semantic tools are `get_next_departures(stop)`,
`get_train_status(train_number, date)`, and a travel subscription that wakes
Mira only when a relevant delay or platform change occurs.

## Conversation backlog outside the integration crawl

These items were discussed alongside Home Assistant integrations but are not
all HA integrations themselves. Repository implementation, HA configuration,
deployment and live acceptance are tracked separately.

| Slice | Current evidence | Remaining work |
| --- | --- | --- |
| Mira read-only email | `search_emails()` and `get_email()` for Gmail and iCloud are implemented on `main` in `mira-home-mcp`, with bounded inert bodies and untrusted-content markings. | Add separate Gmail and iCloud app credentials in Portainer, redeploy, and live-test metadata search plus one explicitly selected message from each account. |
| HA email integrations | No HA IMAP, Google Mail or SMTP entries are configured. This is intentional for v1 rather than an accidental prerequisite gap. | Add HA IMAP only if its event stream gains a filtered subscription use case. Google Mail and iCloud SMTP remain separate future outbound authorities; neither is needed for Mira's direct read-only tools. |
| Mira calendar reading | iCloud `Työ` and `Koti`, the direct Sisu subscription, Holiday and Workday are live in HA; `get_calendar_events()` is implemented. | Put the three personal/schedule `calendar.*` IDs in `HA_CALENDAR_ENTITIES`, redeploy `mira-home-mcp`, and test tomorrow/event windows. Holiday/Workday need not enter Mira's personal-calendar allowlist unless a use case requires them. |
| Calendar mutation | A narrow idempotent `create_calendar_event()` authority and dedicated Mira Inbox calendar are designed. | Implement and deploy the separate write authority; update/delete remain out of scope. |
| Apartment and phone speech | xAI briefing/TTS code and a Finnish-first renderer prompt fragment exist. | Implement explicit `speak_apartment()` and `speak_phone()` tools, routing/presence gates, audio delivery, calling provider policy, and live latency/failure tests. The legacy MiraDB speech path stays excluded. |
| Event subscriptions | MiraRun's subscription-harness work and MiraGen credential forwarding are on upstream `main`; the HA-side desired semantics are documented. | Deploy an actual Mira profile/harness, normalize/authenticate event sources, persist subscriptions and intentions, apply attention filtering, and verify a geofence-to-confirmed-arrival resume flow. |
| Home context MCP | `get_location()`, `get_home_state()` and read-only calendar/email tools are implemented and Compose-managed. | Populate all Portainer entity allowlists with the now-live HA IDs and verify the deployed MCP health/auth plus representative tool calls. Runtime state was not established by the repository audit. |
| Apple Watch and HealthKit | Companion Watch controls were explored; HealthKit ingestion was researched. | Audit and deploy a minimal local-first HealthKit exporter, expose derived sleep/health state rather than raw records, and verify persistent Watch battery/charging telemetry if available. |
| HomeKit Bridge | HA config entry exists. | Curate its include list and pair it with Apple Home only when Siri/Home control becomes useful. |
| Remaining devices | Most apartment devices are live locally. | Put the remaining Tuya LED strip on Wi-Fi/LocalTuya; optionally add System Bridge on Windows 11 for dual-boot continuity. |
| Media stack | Apple TV, LG webOS and speaker integrations are live; Jellyfin/arr was too heavy for the homelab. | Audit network/storage topology, then design a desktop-compute/homelab-storage migration before adding Jellyfin or arr integrations. |
| MiraDeploy | Portainer MCP exists on `main`; GHCR publishing is in draft PR #5. | Repair/re-run the cancelled CI check, review/merge the image workflow, then deploy with a non-admin credential and protected-stack policy. |
| MiraRun/project state | MiraRun has live agent/subscription infrastructure; an HA attention-count projection was proposed. | Define and publish a retained attention-queue state into HA, likely through MQTT or a small semantic integration. Personal-project statistics remain optional; company production telemetry stays in its existing MCPs. |
| Future sensing | Indoor air quality, contact/entry sensors, occupancy sensing, Ruuvi, OBD2 and Finnish transit were discussed. | Choose hardware/data sources before deploying MQTT/ESPHome adapters; treat Wi-Fi silhouette sensing as research, not a near-term occupancy dependency. |
