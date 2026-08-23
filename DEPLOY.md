# Deploying Tealuminati to Oracle Cloud (Always Free)

Target: an always-on Ubuntu ARM VM with a persistent disk, bot managed by systemd.

## 1. Oracle signup (~10 min)

1. Go to https://signup.cloud.oracle.com and create an account.
   - Card details are used for one-time verification only; Always Free resources are never charged.
   - **Home region is permanent** — pick a region showing capacity for Ampere A1 shapes
     (check https://is.gd/oci_capacity or just try; if Mumbai/Hyderabad are tight, pick another).
2. Note your tenancy's home region after signup.

## 2. Create the VM (~5 min)

Console → Compute → Instances → Create Instance:

| Setting | Value |
|---|---|
| Name | `tealuminati` |
| Image | Ubuntu 24.04 Minimal — **aarch64** |
| Shape | Ampere A1.Flex: **2 OCPU / 12 GB RAM** (free quota: 4 OCPU / 24 GB total) |
| SSH keys | Generate a key pair → download BOTH private (.key) and public |
| Networking | defaults (port 22 is open in the default Security List) |

If creation fails with *out of capacity*: retry later, or fall back to
`VM.Standard.E2.1.Micro` (Always Free includes two of them):

| | Ampere A1.Flex | E2.1.Micro (AMD) |
|---|---|---|
| Image architecture | aarch64 | **x86_64** |
| Resources | 2 OCPU / 12 GB | 1 shared OCPU / 1 GB |
| Availability | capacity lottery in many regions | usually instant |

Everything else in this guide — commands, systemd unit, venv, pip — is
identical on both architectures (the bot is pure Python). The micro's
burstable CPU baseline (~12.5%) is still far above what an idle poll-loop
bot uses (~1-2% sustained), and 1 GB RAM comfortably fits it.

Copy the instance's **Public IP address**.

## 3. Server install (~5 min)

From your machine:

```bash
chmod 400 ~/Downloads/ssh-key-*.key
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<PUBLIC_IP>
```

On the server, paste as one block:

```bash
sudo adduser --disabled-password --gecos "" tealuminati
sudo apt-get update && sudo apt-get install -y git python3-venv

sudo mkdir -p /etc/tealuminati
printf 'DISCORD_TOKEN=paste-token-here\nKEEP_ALIVE_ENABLED=false\n' | sudo tee /etc/tealuminati/tealuminati.env >/dev/null
sudo chmod 600 /etc/tealuminati/tealuminati.env

sudo git clone https://github.com/PriyanjanMitra/Tealuminati /opt/tealuminati
cd /opt/tealuminati
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt
sudo chown -R tealuminati:tealuminati /opt/tealuminati

sudo cp deploy/tealuminati.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tealuminati
```

## 4. Verify

```bash
journalctl -u tealuminati -f
```

Expected within ~20 s: gateway connect, `Region monitor started`, then
`Region monitor initialized: N nations` (fresh DB = silent re-baseline).

Persistence check: `sudo reboot`, reconnect, confirm the log says
`Region monitor started (N baseline nations)` with no "initialized" line —
the baseline loaded from SQLite.

## 5. Operating

```bash
# update code
cd /opt/tealuminati && sudo -u tealuminati git pull && sudo systemctl restart tealuminati

# logs / status
journalctl -u tealuminati -f
systemctl status tealuminati
```

- The bot needs **no inbound ports** besides 22 for admin.
- Oracle ephemeral public IPs change on stop/start. Reserve a static IP:
  Console → Networking → IP Management → Reserve Public IP (free while attached).
- Optional hardening later: nightly backup via cron
  (`sqlite3 /opt/tealuminati/tealuminati.db ".backup '/var/backups/tealuminati-$(date +\%F).db'"`),
  `unattended-upgrades`, fail2ban on sshd.

## Shutdown checklist for old hosts

- Laptop: stop the local `main.py` process.
- Render: suspend/delete the service (it was crash-looping on Cloudflare bans).
- Two instances online simultaneously = duplicate notifications.
