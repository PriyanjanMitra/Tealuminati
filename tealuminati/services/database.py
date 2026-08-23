import logging
import sqlite3
import threading
import time
from functools import lru_cache

from tealuminati import config

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS baseline (
    nation TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS stability (
    nation  TEXT PRIMARY KEY,
    counter INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS notified (
    nation        TEXT PRIMARY KEY,
    last_notified REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS ping_roles (
    slot    TEXT PRIMARY KEY,
    role_id INTEGER NOT NULL
);
"""


class Database:
    def __init__(self, path: str | None = None):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path or config.DATABASE_FILE, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ---- meta ----

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def get_meta_int(self, key: str, default: int = 0) -> int:
        raw = self.get_meta(key)
        try:
            return int(raw) if raw is not None else default
        except (TypeError, ValueError):
            return default

    def set_meta(self, key: str, value) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )

    # ---- baseline ----

    def load_baseline(self) -> set[str]:
        return {r["nation"] for r in self._conn.execute("SELECT nation FROM baseline")}

    def save_baseline(self, nations: set[str]) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM baseline")
            self._conn.executemany(
                "INSERT OR IGNORE INTO baseline(nation) VALUES(?)",
                ((n,) for n in sorted(nations)),
            )

    # ---- stability counters ----

    def load_stability(self) -> dict[str, int]:
        return {
            r["nation"]: r["counter"]
            for r in self._conn.execute("SELECT nation, counter FROM stability")
        }

    def save_stability(self, counters: dict[str, int]) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM stability")
            self._conn.executemany(
                "INSERT INTO stability(nation, counter) VALUES(?, ?)",
                sorted((n, c) for n, c in counters.items() if c != 0),
            )

    # ---- notification cooldowns ----

    def load_notified(self) -> dict[str, float]:
        return {
            r["nation"]: r["last_notified"]
            for r in self._conn.execute("SELECT nation, last_notified FROM notified")
        }

    def record_notified(self, nation: str, when: float | None = None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO notified(nation, last_notified) VALUES(?, ?)"
                " ON CONFLICT(nation) DO UPDATE SET last_notified = excluded.last_notified",
                (nation, time.time() if when is None else when),
            )

    def prune_notified(self, older_than: float) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM notified WHERE last_notified < ?", (older_than,))

    # ---- ping roles ----

    def load_ping_roles(self) -> dict[str, int]:
        roles = dict(config.DEFAULT_PING_ROLES)
        for row in self._conn.execute("SELECT slot, role_id FROM ping_roles"):
            roles[row["slot"]] = row["role_id"]
        return roles

    def set_ping_role(self, slot: str, role_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO ping_roles(slot, role_id) VALUES(?, ?)"
                " ON CONFLICT(slot) DO UPDATE SET role_id = excluded.role_id",
                (slot, role_id),
            )


    def close(self) -> None:
        with self._lock:
            self._conn.close()


@lru_cache(maxsize=1)
def get_database() -> Database:
    return Database()
