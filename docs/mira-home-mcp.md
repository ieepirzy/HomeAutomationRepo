# Home Assistant state access for Mira

## Two MCP surfaces, two purposes

Home Assistant already ships a native **Model Context Protocol Server**
integration. Enable it in **Settings → Devices & services → Add integration →
Model Context Protocol Server**. Its Streamable HTTP endpoint is:

```text
http://<home-assistant-host>:8123/api/mcp/assist
```

The built-in Assist surface is useful for interactive Home Assistant control.
It only acts on entities exposed to Assist, and it should remain disabled for
agents that do not need device control.

`services/mira-home-mcp` is the semantic personal-state surface. It exists
because Mira needs stable operations such as `get_location()` and
`get_home_state()` rather than an unrestricted entity dump. The adapter performs
only allowlisted REST reads and never accepts a Home Assistant service call.

## One-time Home Assistant setup

1. Install and sign into the Home Assistant Companion App.
2. Confirm the phone created the intended `device_tracker.*` or `person.*`
   entity under **Settings → Devices & services → Mobile App**.
3. Create named HA zones such as `Home` and `University`.
4. Choose Companion App location privacy:
   - **Zone Name Only** gives the adapter named zones or `outside_known_zones`,
     without coordinates, speed, or an outside-zone address.
   - **Exact** lets `get_location()` return coordinates, accuracy and speed and
     calculate every matching regular/passive HA zone.
5. Enable Geocoded Location for addresses and Activity for movement state if
   those fields are useful. Missing/disabled sensors produce `null`, not guesses.
6. Create a dedicated Home Assistant user for this adapter when practical, then
   create its Long-Lived Access Token. Do not reuse an administrator's personal
   token.

## Portainer configuration

Copy the `Mira Home MCP` variables from `.env.example` into the Portainer stack:

- `MIRA_HOME_MCP_TOKEN`: independent random bearer token for MCP callers.
- `HA_LONG_LIVED_TOKEN`: Home Assistant token used only by the adapter.
- `HA_LOCATION_ENTITY`: authoritative tracker/person entity.
- `HA_ADDRESS_ENTITY`: optional geocoded-location sensor.
- `HA_ACTIVITY_ENTITY`: optional Companion Activity sensor.
- `HA_CALENDAR_ENTITIES`: comma-separated calendar allowlist.
- `HA_*_ENTITIES`: semantic allowlists for occupancy, entries, lights, climate,
  humidity, weather, media, desktop activity, modes and extra state.

After deployment, connect Mira to `http://<home-host>:8423/mcp` over the LAN or
WireGuard using `MIRA_HOME_MCP_TOKEN`.

The MCP response contains precise personal data when HA has it. Scope the MCP
credential to Mira and attach this server only to Miragen profiles that require
home context. Per-agent MCP assignment is the permission boundary; the tool does
not pretend that an authorized agent saw a less precise reading than HA supplied.

## Mira v1 runtime seam

Miragen's Codex executor accepts MCP servers per profile and resolves bearer
tokens from environment-variable names. The Mira profile should mount the shared
Codex subscription home and declare this server along these lines:

```yaml
executor:
  executor: codex
  codex_home: /agent/codex-home
  mcp_servers:
    - name: mira-home
      url: http://homeassistant-host:8423/mcp
      bearer_token_env: MIRA_HOME_MCP_TOKEN
```

`MIRA_HOME_MCP_TOKEN` is forwarded to that agent container through miragend's
explicit environment passthrough. Do not copy its value into the profile.

### Codex default and Grok subscription route

The default Mira v1 route can use Codex with the shared ChatGPT subscription
home. Grok Build is also viable without xAI API billing: xAI officially supports
headless automation and an ACP agent over subscription OAuth, and current
Miragen implements both. Use ACP for Mira because it is the transport that can
receive per-session MCP servers and host permission decisions:

```yaml
executor:
  executor: grok-build
  grok_home: /agent/grok-home
  grok_transport: acp
  mcp_servers:
    - name: mira-home
      url: http://homeassistant-host:8423/mcp
      bearer_token_env: MIRA_HOME_MCP_TOKEN
```

Subscription OAuth applies to Grok Build CLI/ACP. It is not a general credential
for the official `xai-sdk`, REST/Responses, voice, image or video APIs; those use
`XAI_API_KEY` and API billing. Mira's xAI voice therefore remains metered even
when her reasoning turn uses the Grok subscription.

Miragen currently gives Grok executor-job semantics: a successful event run is
terminal rather than one permanent conversation. That is acceptable for v1:
persist subscriptions, pending intentions and relevant history in the event
service, then create a fresh focused run for each matched event. Before granting
Grok broad access, add profile passthrough for Grok's allowed/disallowed-tool and
permission controls so Bash/Edit/file tools can be removed while retaining the
required MCP tools.

### External agents and Origo

The static bearer is the internal v1 credential. If agents outside the trusted
Miragen deployment need access, wrap the MCP ASGI app with Ila's `origo` OAuth
2.1 middleware and expose its protected-resource/authorization discovery. Use
PKCE plus registered clients (or deliberately enabled DCR) and advertise a
dedicated home-read scope. Do not hand external agents the shared internal
bearer.

Origo authenticates clients and binds tokens to the MCP resource; it does not by
itself decide which individual MCP tools a client may invoke. Tool-level access
still needs separate scoped surfaces or an authorization check mapped from the
issued token's scopes. That integration is intentionally deferred until an
external client actually requires it.

### System management through MiraDeploy

Ila's `miradeploy` is already a separate Origo-protected MCP adapter over the
Portainer API. Deploying it on the homelab can give Mira inspection and, when
explicitly authorized, deployment-management capabilities. It remains a
separate high-authority surface and credential from `mira-home` and both speech
tools.

The default Mira profile should receive no mutating MiraDeploy tools. A later
maintenance profile can grant narrowly selected operations with explicit
approval, a non-admin Portainer service account, protected-stack refusals and
mandatory post-change container/log verification. MiraDeploy is not a fallback
for Home Assistant device control.

The current upstream repository does not publish a usable
`ghcr.io/ieepirzy/miradeploy` package and has no container-publish workflow.
For the first homelab deployment, use MiraDeploy's existing Git-backed
Portainer/Compose build. A GHCR image can become the deployment path after the
repository adds a versioned publish workflow and image provenance/upgrade
policy; do not assume an undocumented `latest` image exists.

## iCloud Calendar

Home Assistant represents all calendar providers behind the same calendar
entity contract. Connect iCloud through **Settings -> Devices & services -> Add
Integration -> CalDAV**, use `https://caldav.icloud.com/` as the server, and
authenticate with the Apple ID plus an app-specific password. Keep that
credential in Home Assistant's UI-managed storage, never in Git or Mira's
prompt. Then put only the desired resulting `calendar.*` entities in
`HA_CALENDAR_ENTITIES`.

This boundary is intentional: Mira reads Home Assistant calendar entities and
does not know whether they came from iCloud, Google, a local calendar, or a
future direct adapter. If iCloud CalDAV proves unreliable, its replacement does
not change `get_calendar_events()` or the Sleep Focus bedtime automation.

The tool omits event descriptions, caps results at 100, and returns event
locations only when the caller explicitly asks for them.

CalDAV refreshes on roughly a 15-minute cadence, so it is suitable for bedtime
and morning planning but not second-precise alarms. Treat the HA CalDAV surface
as read context for Mira: the integration exposes calendar and optional task
entities, but does not advertise the create/update/delete actions that some
other calendar providers implement.

### Calendar creation

Add calendar mutation as a separate MCP authority rather than weakening
`mira-home`'s read-only contract. The first operation should be deliberately
narrow:

```text
create_calendar_event(
  title, start, end, all_day=false, location=null,
  source_message_id=null, idempotency_key
)
```

The server writes through iCloud CalDAV using a server-held app-specific
password; the agent never receives that credential. Only one configured
destination calendar is writable. Prefer a dedicated **Mira Inbox** calendar
for events inferred from email so mistakes are visible and reversible. Direct
user requests may target another explicitly allowlisted calendar later.

Creation must return the provider event UID and normalized stored values. The
idempotency key prevents retries or duplicate mail events from creating repeat
appointments, while `source_message_id` records provenance without copying an
entire email body into the calendar. Keep update/delete out of v1 until their
confirmation and conflict semantics are designed.

## Email: inbound context and outbound mail are different capabilities

Email is implemented directly in `mira-home-mcp` with IMAPClient rather than
through Home Assistant. Gmail and iCloud Mail are separate optional accounts
with independent credentials and explicit folder allowlists:

| Provider | Incoming server | Credential | Mira boundary |
| --- | --- | --- | --- |
| Gmail | `imap.gmail.com:993` | Google app password with 2-step verification | General pull-based, read-only mailbox access |
| iCloud Mail | `imap.mail.me.com:993` with SSL | Apple app-specific password | General pull-based, read-only mailbox access |

The read surface and unsolicited event surface are intentionally different.
Read-only tools should support general mailbox use:

```text
search_emails(query="", account=null, folder=null, limit=20)
get_email(locator, include_body=true)
```

`search_emails()` returns lightweight metadata and an opaque locator containing
the account, folder, UIDVALIDITY and UID. `get_email()` retrieves one selected
message. Both select mailboxes read-only and use `BODY.PEEK`; neither operation
marks mail read, moves it, deletes it, or sends a reply. Attachment metadata is
returned, but attachment contents are physically absent from the v1 tool
contract. This lets Mira inspect any individual email when asked or when other
context makes it relevant; access is not limited to bills or calendar-like
messages.

An omitted folder searches the account's configured folder allowlist. Start
with `INBOX`; add the provider's exact Archive or All Mail name after live
verification. The adapter sorts merged results locally instead of trusting
iCloud's advertised server-side sorting behavior.

For v1, incoming email does not start an agent run. Mira calls these tools only
inside a turn that was started for some other reason or by the user. Any future
mail-trigger feature belongs in the separately designed event/subscription
system and must define matching, deduplication and attention policy before it is
enabled. HA's `imap_content` events are available as a possible source, not an
approved Mira trigger.

Email subject, sender and especially body are untrusted external input. Every
email tool result therefore carries `trust.level=untrusted_external_content`
and `instruction_authority=none`, including metadata-only search results. The
adapter retains provider, account, folder, UIDVALIDITY, UID, Message-ID and
receipt time as provenance and avoids copying unnecessary content into context.

That marker does not solve prompt injection. In MiraGen's trust model the model
is the least-trusted process; authority must remain outside it. The adapter
provides a deterministic membrane: bounded fetches, inert visible-text HTML,
no remote-resource fetching, no attachment bodies, and basic phishing signals.
MiraGen profiles, container isolation and host-side gates must bound what a
misled model can do. An eventual email-to-calendar analyst should run with
email-read tools only and emit a typed proposal; a separately authorized
orchestrator or user decides whether to invoke calendar creation.

Extracting a proposed event or bill due date is one workflow built on the
general read surface, not a restriction on it. Mira can present the proposal or
pass it to the separately authorized `create_calendar_event()` tool. The
source email's Message-ID becomes calendar provenance and part of the
idempotency key.

Outbound Gmail and iCloud Mail are planned but remain disabled for v1. Google
Mail uses HA's Google OAuth integration; iCloud can use HA's SMTP integration
with `smtp.mail.me.com:587`, STARTTLS and an Apple app-specific password. Both
belong behind separate `draft_email()` and `send_email()` tools, with sending
requiring destination allowlisting, audit, rate limits and stricter approval.
Do not add either provider's send action to the read-only `mira-home` MCP.

## Bedtime and morning context

This read surface supplies the decision inputs for the first useful Mira
routine: calendar commitments, Sleep/Wake mode, confirmed presence, current
weather and output availability. Sleep Focus can trigger the run, but Mira reads
fresh location/home state before selecting apartment speech, phone speech or no
speech. The same inputs support a morning briefing without another weather API
when HA already owns a suitable weather integration.

Allowlisted `weather.*` entity state supplies current conditions. Modern HA
forecast data is obtained through the response-producing
`weather.get_forecasts` action; add a dedicated read-only `get_weather()`
adapter if forecasts are needed rather than granting Mira generic service-call
authority.

## Next authority boundaries

Do not add these to the read-only MCP server casually:

- `speak_apartment()` routes audio to the apartment speaker/PC endpoint.
- `speak_phone()` makes an outbound call for mobile/car announcements.
- Those are separate tools and permission grants because calling has stricter
  destination allowlisting, consent, rate-limit and failure-handling needs.
- xAI-backed speech receives the renderer-only capability fragment in
  [`docs/mira-voice.md`](mira-voice.md); Mira's identity prompt is designed
  separately and does not inherit the STT demo persona.
- generic external events need authentication, source identity, occurrence and
  receipt timestamps, idempotency, and an append-only record before an agent
  decides whether to speak.
- Home Assistant service calls are device control, not state retrieval.

`speak_apartment()` must re-check a deterministic confirmed-home signal at call
time. If Ila is not confirmed inside, it returns `refused_not_home`; the guard is
not left to the agent prompt. A Home geofence transition alone is too coarse—it
can fire in the driveway or elevator. `speak_phone()` has separate away/mobile
policy and cannot silently fall back to the apartment speaker.

Before selecting either output, Mira calls `get_location()` and, when relevant,
`get_home_state()` unless the triggering event already carries sufficiently
fresh evidence. The output tool still re-checks its guard at execution time to
avoid a stale read between route selection and playback. For example, Sleep
Focus activation expresses intent to hear a bedtime briefing; it does not prove
that the apartment speaker is the correct destination.

### Durable context subscriptions

An event does not always contain enough evidence for an immediate action. Mira
may therefore register a bounded subscription and end its run. A deterministic
watcher persists the subscription and resumes Mira when stronger evidence
arrives or the deadline expires; no model process remains alive and no agent
busy-polls Home Assistant.

The normalized event stream may be persisted for audit and matching, but it is
not forwarded wholesale into the agent. Mira is invoked only for explicitly
high-priority/addressed events or events that match an active subscription. The
subscription set is therefore an attention filter as well as delayed context.

The first deliberately narrow operation should be
`wait_for_confirmed_home(reason, timeout_minutes)`. Confirmation can combine a
Home geofence entry with a later apartment-specific signal such as the front
door, home Wi-Fi/Bluetooth, indoor motion, phone charging or desktop activity.
The resumed event carries the subscription ID, original triggering event,
reason, creation/expiry times and the evidence that matched. A generic predicate
language can wait until real use cases prove it is needed.

The intended flow is:

```text
HA / desktop daemon / external webhook
  → normalized event
  → deterministic persistence and deduplication
  → Mira session
  → optional durable subscription when context is not yet sufficient
  → watcher resumes Mira when evidence matches or the deadline expires
  → explicit speak_apartment() or speak_phone() only when policy permits it
```

For v1 mobile speech, user-initiated conversations can use an HA Companion
Assist pipeline backed by Mira. Spontaneous high-priority speech uses
`speak_phone()`; custom iosMira background audio remains deferred.
