# Zero-Willpower Wake-Up Protocol — implementation notes

This is the companion document the original handoff spec (`WAKEUP_PROTOCOL1.md`)
asked for: discovery findings, every architectural decision that had to be
made without an existing precedent, documented limitations, and setup
steps. Read this before touching `homeassistant/packages/wakeup_protocol.yaml`.

## 1. Repository and host discovery

`HomeAutomationRepo` had no Home Assistant deployment before this change —
it held four small Flask microservices (WiZ lights, LG webOS TV, Apple TV,
a sunrise-time API) built directly against `docker-compose.yaml`, deployed
via Portainer's Git-repository stack feature, with secrets supplied through
a `.env` file consumed as `${VAR}` substitutions in compose. That
`.env`/Portainer-stack-env-vars pattern is real prior art from this
household's other repos (`Loimi` uses the same `${VAR:?error message}`
required-variable convention) and is what this deployment follows too.

**Those four microservices were removed, not ported.** Home Assistant has
native, actively maintained integrations for all of it — `wiz`, `webostv`,
`apple_tv`, and the built-in `sun` integration in place of a custom
sunrise API — so keeping the hand-rolled Flask equivalents would have been
redundant surface area rather than useful continuity. This was confirmed
with the user before deleting them.

**Host architecture:** nothing in the old repo specified a host OS,
orchestrator version, or reverse proxy, and none of that is discoverable
from inside this session. The compose stack below is written to be
portable (a single `network_mode: host` service plus one bridge-network
sidecar) and doesn't assume anything about the host beyond "runs Docker
and is managed by Portainer" — the one fact established by the existing
repository. If the actual host has a reverse proxy, a non-default Docker
network, or a firewall posture that host networking doesn't fit, treat
this as a documented starting assumption to revisit, not a hidden
requirement.

## 2. Deployment architecture

### Docker networking: `network_mode: host` for Home Assistant

Home Assistant needs mDNS/SSDP discovery, the Companion App's local
push-notification handshake, and Apple TV pairing — all of which want
direct LAN access. `network_mode: host` is the supported way to get that
with the official image. This is a deliberate departure from the old
repo's bridge-network-plus-explicit-ports convention (which those four
microservices used because they were simple single-purpose HTTP APIs with
no discovery needs); HA is different enough to warrant it, and it's
explicitly called out as an option in the original spec.

Of the two sidecars, only `briefing` stays on the default bridge network,
publishing to `127.0.0.1` only — Home Assistant (on the host network)
reaches it over loopback, and it's never reachable from the LAN or the
internet. `wake-gateway` is on `network_mode: host` too, since it needs
the opposite property (LAN reachability from the phone) — see section 3
"Wake gateway."

**The callback direction needed its own fix.** `briefing` calling *back*
into Home Assistant when a briefing finishes (its `callback_url`, POSTed
from inside the briefing container) can't use `127.0.0.1:8123` the way
HA's own outbound calls to briefing can — `127.0.0.1` inside a
bridge-network container is that container itself, not the host, so
every callback would silently fail to reach HA. `compose.yaml` maps
`host.docker.internal` to the host gateway on the `briefing` service via
`extra_hosts` (Docker's portable mechanism for this), and the callback
URL built in `homeassistant/packages/wakeup_protocol.yaml`'s
`rest_command` uses that hostname instead of `127.0.0.1`.

### Secrets: `.env` locally, Portainer stack environment variables in production

Matches the existing convention. `.env.example` documents every variable;
real values go in Portainer's per-stack "Environment variables" UI in
production, never committed. Home Assistant's own secrets
(`homeassistant/secrets.yaml`) are a separate mechanism — see below.

### Persistence: git-tracked config, bind-mounted runtime data

```
homeassistant/            git-tracked YAML — the entire declarative config
data/homeassistant/storage/   -> bind-mounted over /config/.storage
data/homeassistant/data/      -> bind-mounted over /config/data (recorder DB)
```

`compose.yaml` mounts `./homeassistant` to `/config`, then mounts
`./data/homeassistant/storage` **over** `/config/.storage` and
`./data/homeassistant/data` **over** `/config/data`. This means:

- Anything git tracks (`configuration.yaml`, `packages/`, `dashboards/`,
  automations expressed declaratively) survives a full volume wipe,
  because it's reconstructed from the repo on every `git pull`.
- Anything Home Assistant writes at runtime (`.storage/` — device
  registry, UI-created integration auth, restored helper state; the
  recorder database) lives physically outside the git working tree
  entirely, in `./data/`, which is gitignored and untouched by however
  Portainer performs a Git redeploy (whether that's an in-place `git
  pull` or something more aggressive doesn't matter — the runtime data
  was never inside the tree it's pulling into).

This sidesteps the actual open question ("does Portainer's Git redeploy
preserve untracked files in the working directory, or does it wipe them?")
rather than depending on the answer. If you're auditing this decision:
the risk this avoids is real — several GitOps tools for Home Assistant
have been bitten by exactly this.

### Configuration model: declarative-by-default, UI for anything with OAuth

Per the spec's explicit request to decide this deliberately:

- **Declarative (git-tracked):** all wake-up-protocol logic — helpers,
  automations, scripts, dashboards. This is the part that must survive a
  volume wipe and be reviewable in a PR, so it's never created through
  the UI.
- **UI-provisioned (persisted in `.storage`, outside git):** anything
  that needs interactive OAuth or device pairing and would be painful or
  impossible to express as YAML — the Companion App / mobile_app
  integration itself, Apple TV pairing, Google/CalDAV calendar (if added
  later), weather integrations if you prefer HA-native weather over the
  briefing service's own OpenWeather call, and the long-lived access
  token used for anything that needs one.

**Caveat worth knowing:** `automations.yaml`, `scripts.yaml`, and
`scenes.yaml` are git-tracked (see `configuration.yaml`) so that they
exist to satisfy HA's `!include` requirement, but the wake-up protocol
itself never touches them — everything lives in the package. **Don't use
the Lovelace/Automation UI editor to create automations you want to
keep.** If you do, HA writes them into `automations.yaml`, which is a
git-tracked file; the next `git pull` can silently discard that edit (or
leave the working tree with an uncommitted local diff that conflicts with
future pulls). If you use the UI editor for something, immediately copy
the result into a package file and revert `automations.yaml`.

## 3. Apple Watch wake detection — what's actually possible

There is no first-party, real-time "the user just woke up" API on iOS or
watchOS. Sleep tracking data (Sleep stages, wake time) lands in the
Health app on a delay and isn't pushed anywhere in real time; HealthKit
background delivery for sleep data is not immediate enough for "lights
ramp on almost immediately" (spec section 9, 10). The routes that were
actually considered:

| Route | Verdict |
|---|---|
| HealthKit sleep-stage background delivery | Rejected — delivery latency is minutes, not seconds; not "almost immediately." |
| Watch/iPhone alarm firing (`Clock` app) | Rejected as the *primary* signal — this is the "phone-only alarm, driven by a fixed clock" the spec explicitly wants to avoid depending on solely. |
| **Sleep Focus transition (asleep → awake) via a Personal Automation** | **Chosen.** iOS Shortcuts' Personal Automations can trigger "When Sleep Focus turns off" (or, if you use a Sleep Schedule without dedicated Focus, "When I wake up" via the Health/Sleep automation trigger available on recent iOS). This is the fastest realistic *un-gated* signal — it fires within roughly a minute of the Sleep Focus ending, not on a fixed clock. |
| A companion watchOS app polling motion/heart-rate | Rejected for v1 — requires shipping and maintaining a custom watchOS app, well outside the scope implied by "adapter boundary + best available fallback." |

**What's actually implemented:** the fallback path from spec section 9,
explicitly, because the ideal (instant, Watch-native wake signal) doesn't
exist:

1. A fixed wake window is defined (`input_datetime.ila_wake_window_start`
   / `_end`, default 05:00–12:00) — outside it, wake events are ignored.
2. Within that window, an iOS Personal Automation triggers on Sleep Focus
   ending and calls a Shortcut that hits a plain `GET` endpoint on
   **`services/wake-gateway`** — a standalone Python service, not a Home
   Assistant webhook (see "Wake gateway" below for why it's a separate
   service).
3. The gateway normalizes that into the `ila_wake_detected` event on
   Home Assistant's event bus, which is what every downstream automation
   actually consumes — nothing in the wake-up logic is coupled to how the
   event got there (spec section 8).

**Documented limitations:**

- **Latency:** typically under a minute from Sleep Focus ending to the
  gateway request landing, but this is bounded by iOS's own
  automation-execution scheduling, not guaranteed. It is meaningfully
  faster than "wait for the fixed alarm clock time," which is the
  property that actually matters here, but it is not sub-second.
- **Reliability:** Personal Automations can silently fail to fire if
  "Ask Before Running" is left enabled (this must be turned off for the
  automation — Settings > Shortcuts, or per-automation) or if the phone
  has no network connectivity when it wakes (the `GET` fails silently
  unless the Shortcut checks the response). Set up a low-battery and
  connectivity check in the Shortcut if this matters to you.
- **False positives:** ending Sleep Focus manually during the night (to
  check the phone) fires the same automation. The `input_boolean.ila_wake_protocol_skip_next`
  control exists partly for this — set it before an intentional
  middle-of-the-night wake, or just accept an occasional early lights-on
  during the wake window (it cannot fire outside 05:00–12:00 regardless).

**Setup required on the phone** (cannot be done from this repository) —
see `services/wake-gateway/README.md` for the full walkthrough:

1. Shortcuts app → Automation → New Personal Automation → Sleep → "When
   Sleep Focus Turns Off" (or your iOS version's equivalent sleep-wake
   trigger).
2. Add action: "Get Contents of URL" → `GET` →
   `http://<home-assistant-host>:8422/wake/<WAKE_TOKEN>` (the value you
   put in `.env` / the Portainer stack env vars).
3. Turn off "Ask Before Running."
4. If the gateway needs to be reachable from outside the home network too
   (edge case: falling asleep away from home), put it behind a VPN
   (WireGuard, matching the pattern `Loimi` already uses) rather than
   forwarding its port directly to the internet.

### Wake gateway — why a standalone Python service instead of an HA webhook

Home Assistant's own `webhook` automation trigger could have handled
this identically — it's a legitimate, simpler alternative and was the
first design in this repo's history. `services/wake-gateway/` exists
instead per explicit design preference: a small, independently
testable/loggable Python service that owns exactly this one
responsibility (receive a `GET` from Shortcuts, normalize it onto Home
Assistant's event bus) without it being one more automation inside a
large HA package. It's genuinely a tradeoff, not a strict improvement —
see `services/wake-gateway/README.md` for the mechanics (it fires events
via Home Assistant's `POST /api/events/<event_type>` REST endpoint,
authenticated with a Long-Lived Access Token generated through the HA UI
after first boot — a manual step, same category as the Companion App
setup).

## 4. Phone-only alarm — mechanism and the Watch-dismissal limitation

**This is the part of the spec most likely to disappoint if left
unexplained, so: read this before assuming the alarm behaves like a
normal iOS alarm.**

Home Assistant cannot make a sound on the phone directly — the Companion
App is a notification/data client, not an alarm engine. The real
mechanism, investigated and chosen:

1. When the wake session starts, Home Assistant sends a **critical**
   push notification via `notify.mobile_app_<device>` (see
   `script.ila_start_alarm`), tagged `ila-wakeup-alarm-start`. Critical
   alerts require the "Critical Alerts" capability to be granted to the
   Home Assistant app in iOS Settings > Notifications > Home Assistant —
   without that permission this silently degrades to a normal
   notification.
2. **This notification is not the alarm.** It is the *trigger* for a
   second iOS Personal Automation ("When I get this notification from
   Home Assistant") that runs a Shortcut which starts a **loud, looping**
   audio session — either a Shortcuts "Play Sound" action wrapped in a
   repeat loop, or (recommended) launching a dedicated alarm app via URL
   scheme (e.g. Alarmy) that is specifically built to be hard to dismiss.
3. On undock, Home Assistant sends a second critical/time-sensitive push
   tagged `ila-wakeup-alarm-stop` (`script.ila_stop_alarm`), which
   triggers a matching "Stop Wake Alarm" Personal Automation that kills
   the loop / calls the alarm app's stop URL scheme.

**Why the indirection matters:** the loop, once started, keeps running
regardless of whether the *originating notification* is dismissed. That's
the load-bearing property.

**The actual limitation — stated plainly, per the spec's requirement not
to silently substitute a weak notification:** a critical push
notification's banner and sound **do mirror to a paired Apple Watch**,
and the Watch lets you dismiss a notification banner from the wrist. If
the phone-side Shortcut automation is triggered purely by the arrival of
that notification and the person swipes it away on the Watch before the
automation runs, the alarm loop may never start.

Two mitigations, both applied, neither fully closes the gap:

- Use a **dedicated alarm app with no Watch companion/mirroring surface**
  (Alarmy and similar apps are explicitly designed this way) rather than
  a bare Shortcuts "Play Sound" loop, so once the automation *does* fire,
  the resulting alarm state is not Watch-dismissible even if the
  triggering notification was.
- watchOS automation-trigger timing for "notification received" fires
  close to instantly on the phone, before a person has realistically had
  time to look at and dismiss it on the Watch — but this is a timing
  argument, not a guarantee.

If you use the stock Clock app instead of a dedicated alarm app for the
Shortcut's action, the resulting alarm **is** Watch-dismissible, same as
any other iOS alarm mirrored there. This document is the disclosure the
spec asked for; it is not fixed by this repository, because it isn't
fixable purely on the Home Assistant side.

**Setup required on the phone:**

1. Settings > Notifications > Home Assistant > turn on Critical Alerts.
2. Shortcuts → Automation → New Personal Automation → App → Home
   Assistant → "Notification received" (filter on the notification
   content if your iOS version supports it, so only
   `ila-wakeup-alarm-start`/`-stop` tagged pushes trigger the respective
   automation) → Run Immediately, Notify Off.
3. Two automations: one starts the alarm loop / opens the alarm app, one
   stops it.

## 5. Phone charger as interlock

Detection: the Companion App's native `sensor.<device>_battery_state`
entity (Charging / Not Charging / Full), which the app updates in the
background. This is the primary path from spec section 13. A second path
exists as the documented fallback in case the Companion App's
battery-state sensor proves too laggy in practice (iOS background
refresh timing is not fully within the app's control): `services/wake-gateway`'s
`GET /undock/<UNDOCK_TOKEN>` endpoint (same mechanism as the wake
detection path in section 3), triggered by a Shortcut on a MagSafe/Qi
accessory disconnect. Both normalize to the same `ila_phone_undocked`
event.

Both paths converge on the same normalized event; the completion
automation (`automation.ila_wakeup_completion`) only *acts* on it while
`input_select.ila_wake_state == waiting_for_phone_undock`, so ordinary
daytime charging/undocking is a no-op by construction, not by a special
case. A 5-second `for:` debounce on the raw charger-state trigger absorbs
charger-contact flapping.

## 6. AI morning briefing

Runs as `services/briefing/` — see `services/briefing/README.md` for the
implementation. Text generation and TTS both use **xAI (Grok)** — chosen
for LLM pricing and TTS quality-per-euro over Anthropic/OpenAI/ElevenLabs,
per household preference. Chat completions go through xAI's
OpenAI-compatible endpoint (the `openai` SDK pointed at
`https://api.x.ai/v1`, default model `grok-4.3` — cheaper than the
flagship `grok-4.5` with the same 1M context, reasonable for a short
daily generation task; override via `XAI_MODEL` if quality matters more
than cost for this particular use). TTS uses xAI's own REST endpoint
directly (`POST /v1/tts`, not OpenAI-compatible). `TTS_PROVIDER=none`
remains a supported fallback — Home Assistant then speaks the generated
text through whatever TTS engine you've configured natively, so a
working briefing never strictly requires a paid TTS call.

xAI also offers a speech-to-text API (`POST /v1/stt`) at $0.10/hour
batch — not wired into anything yet, since no concrete feature in this
protocol currently needs it. Left as a documented option if a
voice-driven feature (e.g. setting today's priorities by speaking
instead of typing into the dashboard) gets scoped later.

Generation starts the instant the alarm does (`script.ila_start_briefing_generation`,
fired via `script.turn_on` so it's fire-and-forget) and reports back
asynchronously via a webhook when done — this is the mechanism that
satisfies "hides non-streaming LLM/TTS latency behind the walk to the
kitchen" without ever blocking lights or alarm. If the briefing isn't
ready by undock, a short deterministic greeting plays immediately and the
full briefing plays the moment the callback lands (still session-gated,
so it never double-plays).

Weather and "today's priorities" are both optional and never invented if
absent — weather from OpenWeatherMap (omitted if unconfigured or the API
call fails), priorities from a freeform dashboard field
(`input_text.ila_todays_priorities`, newline-separated). Calendar
integration was left out of v1: this household doesn't have an existing
calendar OAuth setup in this repo to build on, and inventing one would
mean guessing at a provider. Wiring an existing HA calendar entity into
the briefing payload (the same way `current_streak` and `priorities` are
passed) is a small, contained follow-up once a calendar integration is
configured through the UI.

## 7. Metrics and streaks

Implemented with a deliberate deviation from the spec's suggested helper
list: the 7-day average latency and 30-day success rate are `sensor`
entities (Home Assistant's built-in `statistics` platform, reading the
recorder history of two `input_number` helpers) rather than plain
`input_number` values. A directly-settable `input_number` for a
derived/rolling statistic is a second, driftable source of truth for data
the recorder already has — the `statistics` platform computes it
correctly from history with zero extra bookkeeping. See
`homeassistant/packages/wakeup_protocol.yaml` for the exact entities;
`sensor.ila_7d_average_wake_latency` and `sensor.ila_30d_wake_success_rate`
(plus a `_percent` convenience sensor) replace the spec's suggested
`input_number.ila_7d_average_wake_latency` / `ila_30d_wake_success_rate`.

Streak/session-completion logic (`script.ila_update_streaks_and_metrics`)
is idempotent per session ID via `input_text.ila_last_processed_session_id`,
satisfying "duplicate events must not increment twice" and "restart must
not double-increment" from the same code path — there's exactly one place
streaks get updated, and it's the same whether it's called from a live
completion, a timeout, or restart recovery.

## 8. Restart safety

`automation.ila_wakeup_restart_recovery` runs on every Home Assistant
start and reconciles any session left in `waking`, `waiting_for_phone_undock`,
or `up` (i.e., HA crashed or was redeployed mid-session). Elapsed time is
recomputed explicitly from `input_datetime.ila_last_wake_detected` rather
than relied on via the `for:`-duration triggers elsewhere in the package,
because a restored helper's `last_changed` timestamp is not guaranteed to
survive a restart intact. The phone-side alarm mechanism (section 4) is
entirely independent of Home Assistant's uptime — it's driven by iOS
Personal Automations, not by HA holding a timer open — so a restart
during an active alarm doesn't affect whether the phone is still
sounding; only HA's own bookkeeping needed catching up.

**Two bugs caught in review, both fixed:**

- None of the helpers in this package set `initial:` (deliberately —
  see the comment above the `input_boolean:` block). Home Assistant's
  `input_*` helpers only restore their last value across a restart when
  `initial` is *omitted*; if it's set, the helper force-resets to that
  value on *every* restart, not just the first one. That silently broke
  two things before it was caught: `input_boolean.ila_wake_protocol_skip_next`
  losing a user's pre-bed setting to an overnight Portainer redeploy, and
  `input_select.ila_wake_state` being reset to `idle` before this very
  restart-recovery automation's condition ever got to see whatever state
  a crash had actually left it in — the mechanism described in this
  section was non-functional until that was fixed. First-boot defaults
  (which still need to come from *somewhere*) are now applied exactly
  once by `ila_wakeup_startup_init`, gated on `input_boolean.ila_defaults_applied`
  rather than baked into the helper definitions.
- The branch handling "phone undocked while HA was down" had its
  charger-state check inverted (`condition: not` wrapping the
  `"Not Charging"` match, instead of matching it directly) — it fired on
  the phone still being docked and fell through to "still waiting" on a
  genuine undock, exactly backwards.

## 9. Test mode

`input_boolean.ila_wake_protocol_test_mode` gates two things:

- `script.ila_start_alarm` sends a plain notification instead of the
  critical push that would trigger the real phone-alarm automations —
  test mode structurally cannot ring the real alarm.
- Four simulation scripts (`script.ila_test_simulate_wake`, `_undock`,
  `_duplicate_undock`, `_restart`) fire the same normalized events real
  hardware would, exercising the full state machine end-to-end. All four
  refuse to run unless test mode is on.

The dashboard's Test Mode card only appears while test mode is enabled.

## 10. Deployment steps (Portainer)

1. In Portainer: Stacks → Add stack → Repository, point at this repo and
   branch, build context `/`, compose path `compose.yaml`.
2. Set the stack's Environment variables from `.env.example` — real
   values, including a freshly generated `BRIEFING_AUTH_TOKEN` and
   `XAI_API_KEY`. For `HA_LONG_LIVED_TOKEN`, use the placeholder for now
   — it doesn't exist until step 4.
3. Deploy. On first boot, Home Assistant will not yet have
   `homeassistant/secrets.yaml` — SSH/exec into the host, copy
   `homeassistant/secrets.yaml.example` to `homeassistant/secrets.yaml`
   in the bind-mounted directory, and fill in real values (entity IDs,
   the briefing service bridge URL/token). Restart the `homeassistant`
   container once it exists.
4. Log into Home Assistant → Profile → Security → Long-Lived Access
   Tokens → Create Token. Update `HA_LONG_LIVED_TOKEN` in the Portainer
   stack env vars with the real value and redeploy — this is what lets
   `services/wake-gateway` fire events into Home Assistant (see section 3
   "Wake gateway").
5. Complete the Companion App setup (mobile_app integration, Critical
   Alerts permission) and the two iOS Personal Automations from sections
   3 and 4 above.
6. Redeploy from Portainer ("Pull and redeploy") on every subsequent git
   push to update the declarative config; `homeassistant/secrets.yaml`
   and everything under `data/` are untouched by this, per section 2.

## 11. Acceptance criteria (self-assessed against `WAKEUP_PROTOCOL1.md` §24)

- [x] Portainer Git-deployable Compose stack (`compose.yaml`).
- [x] Home Assistant configuration version-controlled (`homeassistant/`).
- [x] Runtime data and secrets excluded from git (`.gitignore`, `data/`,
      `secrets.yaml`).
- [x] Wake detection enters a normalized state machine
      (`ila_wake_detected` event → `input_select.ila_wake_state`).
- [x] Lights ramp immediately (`script.ila_start_lights`, fired in
      `parallel:` alongside the alarm, never behind the briefing).
- [x] Phone-only alarm starts — with the Watch-dismissal caveat
      documented in section 4, not silently glossed over.
- [x] Briefing generation starts concurrently, fire-and-forget.
- [x] Phone removal detected (Companion App battery-state sensor +
      Shortcut webhook fallback).
- [x] Undock stops the alarm.
- [x] Launch latency stored (`input_number.ila_launch_latency_seconds`,
      rolled up by `sensor.ila_7d_average_wake_latency`).
- [x] Streak updates exactly once per session (idempotency guard).
- [x] Briefing plays after undock when available; deterministic greeting
      otherwise.
- [x] AI/TTS failure doesn't break the wake flow (every external call is
      wrapped and falls back).
- [x] Daytime charger events ignored (state-gated on active session).
- [x] Redeploy/restart don't duplicate effects (persistence model +
      restart recovery automation).
- [x] Test mode exists and cannot trigger the production alarm.
- [x] Apple-platform limitations documented (sections 3 and 4).
- [x] No NFC tag required.
- [x] No return-to-bed detection implemented (explicit non-goal, per spec §25).
