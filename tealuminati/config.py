import os

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

REGION_NAME = os.getenv("REGION_NAME", "Britannia")
REGION_MONITOR_ENABLED = _bool("REGION_MONITOR_ENABLED", True)

NOTIFICATION_CHANNEL_ID = _int("NOTIFICATION_CHANNEL_ID", 1493815461349953616)

CHECK_INTERVAL = _int("CHECK_INTERVAL", 10)
RMB_CHECK_INTERVAL = _int("RMB_CHECK_INTERVAL", 10)

JOIN_THRESHOLD = _int("JOIN_THRESHOLD", 3)
LEAVE_THRESHOLD = _int("LEAVE_THRESHOLD", 20)
NOTIFY_COOLDOWN_SECONDS = _int("NOTIFY_COOLDOWN_SECONDS", 300)
STARTUP_GRACE_CHECKS = _int("STARTUP_GRACE_CHECKS", 20)
SANITY_MIN_BASELINE = _int("SANITY_MIN_BASELINE", 10)
SANITY_MIN_RATIO = 0.5

DATABASE_FILE = os.getenv("DATABASE_FILE", "tealuminati.db")

KEEP_ALIVE_ENABLED = _bool("KEEP_ALIVE_ENABLED", True)
KEEP_ALIVE_PORT = _int("KEEP_ALIVE_PORT", 8080)

PING_ROLE_ORDER = ("home", "deputy", "prime_minister", "cabinet_secretary")
DEFAULT_PING_ROLES = {
    "home": 1493383252290048000,
    "deputy": 1493384004064247909,
    "prime_minister": 1493383007808131102,
    "cabinet_secretary": 1493383060660420628,
}
