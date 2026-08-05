# HomeAutomationRepo

Home Assistant deployment for Ila's apartment, centered on the
**Zero-Willpower Wake-Up Protocol**: lights ramp on, a phone-only alarm
starts, and an AI morning briefing generates concurrently — the whole
thing only stops when the phone is physically removed from its kitchen
charger, forcing a walk out of bed.

Full design, discovery findings, and every documented assumption/tradeoff
live in **[`docs/wakeup-protocol.md`](docs/wakeup-protocol.md)** — read
that before making changes, especially before touching
`homeassistant/packages/wakeup_protocol.yaml`.

## Repository layout

```
compose.yaml              Production Compose stack (Portainer Git-deployed)
.env.example               Template for Portainer stack / local .env
homeassistant/              Git-tracked Home Assistant configuration
  configuration.yaml
  automations.yaml / scripts.yaml / scenes.yaml   (reserved — see docs)
  secrets.yaml.example      Copy to secrets.yaml on the host, fill in real values
  packages/
    wakeup_protocol.yaml     Everything for the wake-up subsystem
  dashboards/
    wakeup.yaml
  www/briefing/              Briefing audio published here at runtime (gitignored)
services/
  briefing/                  LLM + TTS microservice for the morning briefing
data/                        Runtime data (recorder DB, .storage, briefing cache) — gitignored
docs/
  wakeup-protocol.md          Design doc, assumptions, setup steps
```

## Quick start (Portainer)

See `docs/wakeup-protocol.md` §10 for the full walkthrough. Short version:
point a Portainer stack at this repo/branch with compose path
`compose.yaml`, set the environment variables from `.env.example`, deploy,
then copy `homeassistant/secrets.yaml.example` to
`homeassistant/secrets.yaml` on the host and fill in real values (that
file is intentionally not managed by git — see `docs/wakeup-protocol.md`
§2 "Persistence").

## History

This repo previously held four standalone Flask microservices (WiZ
lights, LG webOS TV, Apple TV, sunrise time) driven by a bare
`docker-compose.yaml`. They were retired in favor of Home Assistant's
native integrations for the same devices — see
`docs/wakeup-protocol.md` §1 for why.
