# Tealuminati

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/discord.py-v2.0+-blueviolet.svg)](https://github.com/Rapptz/discord.py)
[![NationStates API](https://img.shields.io/badge/NationStates-SSE%20%2B%20REST-green.svg)](https://www.nationstates.net/pages/api.html)
[![Database](https://img.shields.io/badge/database-SQLite%20WAL-lightgrey.svg)](https://www.sqlite.org/)

A high-reliability Discord bot engineered for real-time NationStates region intelligence. Configured out of the box for the region **Britannia**, Tealuminati provides instantaneous alerts for regional movements, World Assembly status transitions, and Regional Message Board (RMB) posts with configurable government role notifications.

---

## Architecture Overview

Tealuminati utilizes a dual-pipeline architecture combining sub-second push streaming with periodic reconciliation polling:

```mermaid
flowchart TD
    subgraph NationStates ["NationStates Servers"]
        SSEStream["Live Happenings SSE Stream<br/><code>/api/rmb+move+founding+cte+eject+member/region:name</code>"]
        RestAPI["Regional Shard REST API<br/><code>q=nations / q=wanations / q=messages</code>"]
    end

    subgraph BotServices ["Tealuminati Services"]
        SSEClient["SSEClient (sse.py)<br/>• Auto-reconnect with backoff<br/>• Last-Event-ID resumption"]
        RestFetchers["API Services (nations_api.py, rmb_api.py)<br/>• XML parsing & sanitization<br/>• Ratio-based sanity filters"]
        SQLiteDB[("SQLite WAL Database (database.py)<br/>• Baselines & stability counters<br/>• Last event & post IDs<br/>• Ping role configurations")]
    end

    subgraph Cogs ["Discord Cogs / Monitors"]
        RegionCog["RegionMonitor<br/>Foundings, Moves, CTEs, Ejections"]
        WACog["WaMonitor<br/>Admissions, Resignations, Immigrations"]
        RMBCog["RmbMonitor<br/>Message stream & formatted previews"]
        AdminCog["AdminCommands<br/>Status, Backup, Role Management"]
    end

    subgraph Discord ["Discord Server"]
        AlertChannel["Notification Channel<br/>• Embeds with direct NS links<br/>• Government role pings"]
    end

    SSEStream -->|Push Events| SSEClient
    RestAPI -->|Reconcile (5 min)| RestFetchers

    SSEClient -->|Real-time dispatch| RegionCog
    SSEClient -->|Real-time dispatch| WACog
    SSEClient -->|Real-time dispatch| RMBCog

    RestFetchers -->|Baseline verification| RegionCog
    RestFetchers -->|Baseline verification| WACog
    RestFetchers -->|Catch-up fallback| RMBCog

    RegionCog <--> SQLiteDB
    WACog <--> SQLiteDB
    RMBCog <--> SQLiteDB
    AdminCog <--> SQLiteDB

    RegionCog -->|Alerts| AlertChannel
    WACog -->|Alerts| AlertChannel
    RMBCog -->|Alerts| AlertChannel
```

---

## Key Features

### 1. Live Happenings SSE Streaming (Real-Time)
- Connects directly to the NationStates Server-Sent Events endpoint:  
  `/api/rmb+move+founding+cte+eject+member/region:<region_name>`
- Delivers events to Discord within milliseconds with zero rate-limit polling overhead.
- Features resilient reconnection with exponential backoff and tracks `Last-Event-ID` in SQLite for lossless event replay across restarts and transient network drops.

### 2. Regional Residency Monitor
- **Real-Time Joins**: Catches new nation foundings, refoundings, and relocations entering the region.
- **Real-Time Departures**: Detects relocations out of the region, ejections, and Ceased to Exist (CTE) events.
- **Hysteresis Debounce Engine**: Background periodic checks verify the baseline roster using configurable stability counters (`JOIN_THRESHOLD`, `LEAVE_THRESHOLD`) to prevent phantom flip-flopping during upstream API outages.
- **Sanity Protection**: Rejects corrupted or severely truncated upstream API responses (`SANITY_MIN_RATIO = 0.5`) so network glitches never trigger accidental mass-departure notifications.

### 3. World Assembly (WA) Monitor
- **Resident Admissions**: Alerts immediately when an existing resident joins the World Assembly.
- **Resident Resignations**: Alerts immediately when a resident resigns from the World Assembly.
- **Immigration / Emigration**: Intelligently distinguishes between resident status changes and WA members moving into or out of the region.
- **Legacy Shard Compatibility**: Automatically parses both modern `<WANATIONS>` and legacy `<UNNATIONS>` XML tags returned by the NationStates API.

### 4. Regional Message Board (RMB) Monitor
- Relays new RMB posts in real-time as rich Discord embeds.
- Includes author name, likes count, formatted message excerpt (up to 500 characters), exact post timestamp, and direct links to the regional board.
- Automatically seeds to the newest post on cold boot to prevent historical spam.

### 5. Government Role Notifications
- Supports targeted role mentions for four government positions:
  - **Home Office**
  - **Deputy Prime Minister**
  - **Prime Minister**
  - **Cabinet Secretary**
- Configurable dynamically via Discord commands and persisted in SQLite.

### 6. Persistence & Self-Healing
- Powered by a SQLite database in **WAL (Write-Ahead Logging)** mode for concurrency safety.
- Survives reboots, bot restarts, and server migrations without data loss.
- **Silent Boot Seeding**: On a clean database start, baseline rosters and RMB positions are seeded silently without spamming notifications.

---

## Discord Commands

| Command | Permission | Arguments | Description |
|---|---|---|---|
| `!status` | Everyone | None | Comprehensive diagnostic summary: region name, SSE stream status, total checks, nation counts, baseline size, pending changes, WA counts, and RMB post ID. |
| `!ssestatus` | Everyone | None | Detailed SSE stream diagnostics: live connection state, current `Last-Event-ID`, reconnect count, reconcile interval, and active target event buckets. |
| `!wastatus` | Everyone | None | World Assembly monitor metrics: current WA nations, baseline size, pending debounce changes, check interval, and join/leave thresholds. |
| `!rmbstatus` | Everyone | None | RMB monitor status: stream mode (SSE vs. polling), last recorded post ID, check interval, and current ping role assignments. |
| `!forcecheck` | Everyone | None | Manually triggers an immediate reconciliation cycle against the NationStates REST API for both region residency and WA status. |
| `!backupnow` | Administrator | None | Generates and sends a downloadable `known_nations_backup.json` file containing the complete roster and metadata snapshot. |
| `!setpingroles` | Administrator | `[@home] [@deputy] [@pm] [@cabinet]` | Configures the Discord role mentions for the four government slots. Omitted arguments retain their previous values. |

---

## Configuration Reference

All settings are configured via environment variables (or a `.env` file in the project root):

| Variable | Default | Type | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | *(Required)* | String | Discord Bot Token from the Discord Developer Portal. |
| `REGION_NAME` | `Britannia` | String | Target NationStates region to monitor (case-insensitive). |
| `REGION_MONITOR_ENABLED` | `true` | Boolean | Enable or disable the regional residency monitor cog. |
| `WA_MONITOR_ENABLED` | `true` | Boolean | Enable or disable the World Assembly monitor cog. |
| `SSE_ENABLED` | `true` | Boolean | Enable real-time NationStates Live Happenings SSE push streaming. |
| `NOTIFICATION_CHANNEL_ID` | *(Britannia ID)* | Integer | Discord text channel snowflake ID where alerts and embeds are dispatched. |
| `RECONCILE_INTERVAL` | `300` | Integer | Interval (seconds) between background baseline reconciliation polls when SSE is active (default 5 minutes). |
| `CHECK_INTERVAL` | `10` | Integer | Polling fallback interval (seconds) for region residency if SSE is disabled. |
| `WA_CHECK_INTERVAL` | `10` | Integer | Polling fallback interval (seconds) for WA nations if SSE is disabled. |
| `RMB_CHECK_INTERVAL` | `10` | Integer | Polling fallback interval (seconds) for RMB messages if SSE is disabled. |
| `JOIN_THRESHOLD` | `3` | Integer | Consecutive polling cycles required to confirm an unannounced nation join. |
| `LEAVE_THRESHOLD` | `20` | Integer | Consecutive polling cycles required to confirm an unannounced nation departure. |
| `WA_JOIN_THRESHOLD` | `3` | Integer | Consecutive cycles required to confirm an unannounced WA admission. |
| `WA_LEAVE_THRESHOLD` | `20` | Integer | Consecutive cycles required to confirm an unannounced WA resignation. |
| `DATABASE_FILE` | `tealuminati.db` | String | Path to the SQLite database file for state persistence. |
| `KEEP_ALIVE_ENABLED` | `true` | Boolean | Starts a lightweight background HTTP health server for container hosting platforms. |
| `KEEP_ALIVE_PORT` | `8080` | Integer | Port bound by the HTTP keep-alive server. |

---

## Local Setup & Development

### Prerequisites
- **Python 3.10** or higher
- A registered **Discord Application & Bot** with **Message Content Intent** enabled:
  1. Navigate to the [Discord Developer Portal](https://discord.com/developers/applications).
  2. Select your application &rarr; **Bot**.
  3. Under **Privileged Gateway Intents**, turn on **Message Content Intent**.

### Step-by-Step Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/PriyanjanMitra/Tealuminati.git
   cd Tealuminati
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and fill in your `DISCORD_TOKEN` and target `NOTIFICATION_CHANNEL_ID`.

5. **Start the bot**:
   ```bash
   python main.py
   ```

---

## Production Deployment (systemd)

Tealuminati ships with a ready-to-use systemd service unit located at `deploy/tealuminati.service`.

### Recommended Setup on Debian / Ubuntu

1. **Create a dedicated system user**:
   ```bash
   sudo useradd -r -s /bin/false -d /opt/tealuminati tealuminati
   ```

2. **Install code and dependencies to `/opt/tealuminati`**:
   ```bash
   sudo mkdir -p /opt/tealuminati
   sudo git clone https://github.com/PriyanjanMitra/Tealuminati.git /opt/tealuminati
   cd /opt/tealuminati
   sudo python3 -m venv .venv
   sudo /opt/tealuminati/.venv/bin/pip install -r requirements.txt
   sudo chown -R tealuminati:tealuminati /opt/tealuminati
   ```

3. **Configure environment file with restricted permissions**:
   ```bash
   sudo mkdir -p /etc/tealuminati
   sudo cp /opt/tealuminati/.env.example /etc/tealuminati/tealuminati.env
   sudo nano /etc/tealuminati/tealuminati.env  # Add DISCORD_TOKEN, KEEP_ALIVE_ENABLED=false, etc.
   sudo chown -R tealuminati:tealuminati /etc/tealuminati
   sudo chmod 600 /etc/tealuminati/tealuminati.env
   ```

4. **Install and activate the systemd service**:
   ```bash
   sudo cp deploy/tealuminati.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now tealuminati
   ```

5. **Inspect live operational logs**:
   ```bash
   journalctl -u tealuminati -f
   ```

---

## Running Tests

Tealuminati includes a comprehensive test suite covering the persistence layer, hysteresis stability counters, NationStates XML shard parsing, and live SSE event dispatching.

Run all tests via Python's built-in test runner:

```bash
python -m unittest discover tests
```

### Test Suite Structure
- `tests/test_database.py`: Verifies SQLite schema creation, CRUD operations, metadata storage, and baseline synchronization.
- `tests/test_region_logic.py`: Tests the pure debounce algorithms, counter increments/decrements, and threshold confirmations.
- `tests/test_parsing.py`: Validates XML handling for nation rosters and legacy `<UNNATIONS>` / `<WANATIONS>` compatibility.
- `tests/test_wa_monitor.py`: Validates WA monitor state machine, immigration vs. resident status detection, and API sanity ratios.
- `tests/test_sse.py`: Tests Server-Sent Events line framing, regex parsing for movements/foundings/ejections/CTEs, and callback dispatching.

---

## Project Structure

```text
Tealuminati/
├── deploy/
│   └── tealuminati.service      # Systemd unit file for production deployment
├── tealuminati/
│   ├── __init__.py
│   ├── bot.py                   # Discord Bot client, cog setup, SSE lifecycle hooks
│   ├── config.py                # Environment-driven configuration variables
│   ├── keep_alive.py            # Lightweight Flask web server for container health checks
│   ├── models.py                # Dataclasses (RmbPost, etc.)
│   ├── pings.py                 # Role mention resolution helpers
│   ├── cogs/
│   │   ├── admin_commands.py    # Diagnostic and administration Discord commands
│   │   ├── region_monitor.py    # Nation residency and movement monitor
│   │   ├── rmb_monitor.py       # Regional Message Board monitor and embed relay
│   │   └── wa_monitor.py        # World Assembly residency and transition monitor
│   ├── services/
│   │   ├── database.py          # SQLite WAL persistence layer
│   │   ├── nations_api.py       # NationStates REST API client (region & WA nations)
│   │   ├── region_logic.py      # Pure hysteresis debounce logic
│   │   ├── rmb_api.py           # NationStates REST API client for RMB messages
│   │   └── sse.py               # Real-time Live Happenings Server-Sent Events client
│   └── views/
│       └── embeds.py            # Formatted Discord embed builders
├── tests/                       # Unit test suite
├── .env.example                 # Example configuration template
├── main.py                      # Application entrypoint
├── requirements.txt             # Python package dependencies
└── README.md                    # Project documentation
```

---

## License

This project is licensed under the [MIT License](LICENSE).
