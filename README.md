# Tealuminati

A Discord bot that monitors the NationStates region **Britannia**: it announces
nations joining/leaving the region and relays new Regional Message Board (RMB) posts,
with role pings for government roles.

## Features

- **Region monitor** — polls the NationStates API every 10 s and announces
  confirmed joins (~30 s) and departures (~3.5 min) with embeds.
  Debounce thresholds suppress false alarms from API flakiness; a startup grace
  period and per-nation cooldown prevent ping spam.
- **RMB monitor** — polls the latest RMB posts every 10 s and relays any new post
  as an embedded message with role pings.
- **SQLite persistence** — baseline roster, pending-change counters, notification
  cooldowns and ping-role settings survive restarts in `tealuminati.db`.
  No JSON state files, no periodic git commits.
- **Self-healing** — after a fresh start or data loss the bot silently rebuilds its
  baseline from the live region and re-seeds its RMB position without notifying.

## Commands

| Command | Permission | Effect |
|---|---|---|
| `!status` | anyone | Region/RMB status summary |
| `!forcecheck` | anyone | Trigger an immediate region poll |
| `!backupnow` | administrator | Post a JSON snapshot of the roster as a file |
| `!setpingroles` | administrator | Set the four government ping roles (shared by both monitors) |
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
intervals, join/leave thresholds, notification cooldown, channel ID, database path,
keep-alive port. Defaults match the current Britannia setup.

## Deployment

See [DEPLOY.md](DEPLOY.md) for hosting on an Oracle Cloud Always-Free VM with
systemd (works unchanged on AMD/x86_64 or ARM).

## Tests

```bash
python -m unittest discover tests
```

Covers the SQLite layer, debounce/threshold/cooldown logic, and NationStates XML parsing.

## Layout

```
tealuminati/
  bot.py               entry point: intents, cog loading
  config.py            env-driven settings
  services/
    database.py        SQLite persistence layer
    nations_api.py     region roster fetch/parse
    rmb_api.py         RMB post fetch/parse
    region_logic.py    pure debounce/threshold logic (unit-tested)
  cogs/
    region_monitor.py  join/leave detection and announcements
    rmb_monitor.py     RMB relay
    admin_commands.py  !commands
  views/embeds.py      Discord embed builders
tests/                 unit tests
deploy/                systemd unit
```
