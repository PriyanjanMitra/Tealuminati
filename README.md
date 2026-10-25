# Tealuminati

A Discord bot that monitors the NationStates region **Britannia**: it announces
nations joining/leaving the region, tracks World Assembly entries/exits in the region,
and relays new Regional Message Board (RMB) posts, with role pings for government roles.

## Features

- **Live Happenings SSE Streaming** — connects directly to the NationStates Server-Sent
  Events API (`/api/rmb+move+founding+cte+eject+member/region:britannia`) for sub-second,
  real-time event delivery with zero rate-limit polling overhead.
  Supports `Last-Event-ID` automatic replay upon reconnection.
- **Region monitor** — captures real-time joins (foundings, relocations) and departures
  (relocations, ejections, CTEs), with periodic baseline reconciliation.
- **World Assembly monitor** — tracks World Assembly admissions and resignations in real-time,
  distinguishing between resident status changes and WA members moving into/out of the region,
  complete with role pings.
- **RMB monitor** — receives real-time RMB posts via SSE with zero polling delay,
  relaying messages with government role pings and automatic seeding on restart.
- **SQLite persistence** — baseline roster, WA baseline, pending-change counters,
  SSE event position, and ping-role settings survive restarts in `tealuminati.db`.
- **Self-healing** — after a fresh start or data loss the bot silently rebuilds its
  baseline from the live region and re-seeds its position without notification spam.

## Commands

| Command | Permission | Effect |
|---|---|---|
| `!status` | anyone | Region, WA, RMB, and SSE stream status summary |
| `!ssestatus` | anyone | Live SSE stream diagnostics, event IDs, and reconnect stats |
| `!forcecheck` | anyone | Trigger an immediate region and WA reconciliation poll |
| `!backupnow` | administrator | Post a JSON snapshot of the roster as a file |
| `!setpingroles` | administrator | Set the four government ping roles (shared by monitors) |
| `!wastatus` | anyone | World Assembly monitor status and configuration |
| `!rmbstatus` | anyone | RMB monitor position and ping configuration |

## Setup (local)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your DISCORD_TOKEN
python main.py
```

Requires Python 3.10+. The Discord bot needs the *Message Content* intent enabled
in the Developer Portal.

## Configuration

All values are environment variables (see `.env.example`): region name, check
intervals, join/leave thresholds, channel ID, database path,
keep-alive port. Defaults match the current Britannia setup.

## Hosting

Run it on any always-on Linux machine (x86_64 or ARM) — a VM or a spare
laptop with plain Debian works well. A ready-made systemd unit ships in
`deploy/tealuminati.service`. It expects:

- the repo cloned to `/opt/tealuminati` with a virtualenv at `.venv/`
- env vars in `/etc/tealuminati/tealuminati.env` (mode 600) containing at
  minimum `DISCORD_TOKEN=...` and `KEEP_ALIVE_ENABLED=false`
- a non-root user `tealuminati` owning `/opt/tealuminati`

```bash
sudo cp deploy/tealuminati.service /etc/systemd/system/
sudo systemctl enable --now tealuminati
journalctl -u tealuminati -f
```

## Tests

```bash
python -m unittest discover tests
```

Covers the SQLite layer, debounce/threshold logic, and NationStates XML parsing.

## Layout

```
tealuminati/
  bot.py               entry point: intents, cog loading
  config.py            env-driven settings
  services/
    database.py        SQLite persistence layer
    nations_api.py     region roster fetch/parse
    rmb_api.py         RMB post fetch/parse
    sse.py             NationStates Live Happenings SSE client
    region_logic.py    pure debounce/threshold logic (unit-tested)
  cogs/
    region_monitor.py  join/leave detection and announcements
    wa_monitor.py      World Assembly admission/resignation detection
    rmb_monitor.py     RMB relay
    admin_commands.py  !commands
  views/embeds.py      Discord embed builders
tests/                 unit tests
deploy/                systemd unit
```
