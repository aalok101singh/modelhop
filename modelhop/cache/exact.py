"""SQLite-backed exact cache (v1.1 W1)."""

from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional


def cache_key(
    normalized_query: str,
    model_set_version: str,
    policy_version: str,
    tenant: str,
    trust_hash: str = "",
) -> str:
    raw = "|".join(
        [normalized_query.strip().lower(), model_set_version, policy_version, tenant, trust_hash]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ExactCache:
    def __init__(self, path: Optional[str] = None, ttl_s: int = 86400, max_entries: int = 5000):
        self.path = Path(path) if path else Path("modelhop_cache.sqlite")
        self.ttl_s = ttl_s
        self.max_entries = max_entries
        self._init()

    def _init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # NOTE: sqlite3.Connection.__exit__ commits but does NOT close;
        # closing() prevents ResourceWarning leaks.
        with contextlib.closing(sqlite3.connect(str(self.path))) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL,
                    created REAL NOT NULL, accessed REAL NOT NULL
                )""")
            conn.commit()

    def get(self, key: str) -> Optional[dict]:
        now = time.time()
        with contextlib.closing(sqlite3.connect(str(self.path))) as conn:
            row = conn.execute("SELECT value, created FROM cache WHERE key=?", (key,)).fetchone()
            if not row:
                return None
            value, created = row
            if (now - float(created)) > self.ttl_s:
                conn.execute("DELETE FROM cache WHERE key=?", (key,))
                conn.commit()
                return None
            conn.execute("UPDATE cache SET accessed=? WHERE key=?", (now, key))
            conn.commit()
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None

    def put(self, key: str, value: dict) -> None:
        now = time.time()
        with contextlib.closing(sqlite3.connect(str(self.path))) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, created, accessed) VALUES (?,?,?,?)",
                (key, json.dumps(value, default=str), now, now),
            )
            # LRU eviction.
            count = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            if count > self.max_entries:
                overflow = count - self.max_entries
                conn.execute(
                    "DELETE FROM cache WHERE key IN (SELECT key FROM cache ORDER BY accessed ASC LIMIT ?)",
                    (overflow,),
                )
            conn.commit()

    def invalidate(self) -> None:
        with contextlib.closing(sqlite3.connect(str(self.path))) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()
