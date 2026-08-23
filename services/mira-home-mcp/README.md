# Mira Home MCP

Read-only semantic tools backed by Home Assistant:

- `get_location()`
- `get_calendar_events(day_offset=1, days=1, include_locations=false)`
- `get_home_state()`
- `search_emails(query="", account=null, folder=null, limit=20)`
- `get_email(locator, include_body=true)`

The service intentionally does not expose generic entity reads, service calls,
speech, or device control. Those are different authority boundaries. Its Home
Assistant token reads the source system; callers authenticate separately with
`MIRA_HOME_MCP_TOKEN`.

Tool results use an explicit `ok` envelope. `ok: false` means Home Assistant
could not be read or the server is not configured for that operation; an empty
successful list means the read completed and found nothing.

## Location contract

`get_location()` returns the named zone plus coordinates, accuracy, speed,
address and Companion activity state whenever those sources are configured and
currently available. It returns every matching zone, including overlapping or
passive zones. With **Zone Name Only** configured in Companion, it falls back to
the tracker state and precise fields are `null`.

Every source includes its own update timestamp/age. iOS controls background
location cadence, so callers must not treat an old observation as live state.

`get_home_state()` groups explicitly configured entity IDs into occupancy,
entries, lights, climate, humidity, weather, media, desktop activity, modes and
other.
The MCP credential grants access to this data; narrow access at the Miragen
agent boundary by attaching this MCP only to agents that require home context.

Speed is reported when present, with a cautious motion label. The adapter never
claims that Ila is driving based solely on speed.

## Run locally

Set the variables documented in `.env.example`, then:

```bash
docker compose --env-file .env up --build mira-home-mcp
```

The Streamable HTTP endpoint is `http://<home-host>:8423/mcp`; send
`Authorization: Bearer <MIRA_HOME_MCP_TOKEN>`. Keep it on the LAN or WireGuard.
Do not forward port 8423 directly to the public internet.

The health endpoint is unauthenticated at `/healthz` and reveals only service
health, not Home Assistant connectivity or state.

## Email trust boundary

Gmail and iCloud Mail are optional direct IMAPClient transports; they are not
routed through Home Assistant. Both use TLS, app-specific passwords, read-only
mailbox selection, stable UIDs and `BODY.PEEK` fetches. Search is limited to the
folders configured for that account.

The v1 binary contains no SMTP client and exposes no mail mutation tools. It
cannot mark read, flag, move, delete, draft, reply or send. Bodies are size- and
character-bounded, HTML is reduced to inert visible text, remote resources are
not fetched, and attachment contents are not returned.

Every search result and retrieved message carries
`trust.level=untrusted_external_content` and
`instruction_authority=none`. This is provenance, not a claim that prompt
injection has been solved. MiraGen must still treat the model as the
least-trusted process and constrain consequential actions at its profile,
container and host-policy boundaries.

After configuring credentials, verify each provider/folder without printing any
mail content:

```bash
docker compose run --rm mira-home-mcp python -m app.verify_imap
```

The smoke test confirms the folder can be selected read-only, UIDVALIDITY is
available, and a `BODY.PEEK` header fetch does not change the selected message's
flags. An empty folder is reported with the PEEK comparison untested.
