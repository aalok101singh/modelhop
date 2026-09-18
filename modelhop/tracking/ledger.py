"""Hash-chained, HMAC-signed decision ledger (v1.1 W3)."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from ..core.persistence import SignedStore

GENESIS_HASH = "00" * 32


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


class LedgerEntry(dict):
    pass


class DecisionLedger:
    """Append-only ledger with hash chain + HMAC.

    Each entry: seq, ts, prev_hash, payload_hash, payload, mac.
    """

    def __init__(self, path: Optional[str] = None, store: Optional[SignedStore] = None):
        self.path = Path(path) if path else Path("modelhop_ledger.jsonl")
        self.store = store or SignedStore(schema_version=1)
        self._entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        self._entries = []
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self._entries.append(entry)
        except OSError:
            return

    def _persist_entry(self, entry: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            pass

    def append(self, event: dict) -> dict:
        seq = len(self._entries)
        prev_hash = self._entries[-1]["payload_hash"] if self._entries else GENESIS_HASH
        payload_hash = hashlib.sha256(_canonical(event)).hexdigest()
        ts = datetime.now(timezone.utc).isoformat()
        mac = hmac.new(self.store.key, _canonical(event), hashlib.sha256).hexdigest()
        entry = {
            "seq": seq,
            "ts": ts,
            "prev_hash": prev_hash,
            "payload_hash": payload_hash,
            "payload": event,
            "mac": mac,
        }
        self._entries.append(entry)
        self._persist_entry(entry)
        return entry

    def verify_chain(self) -> tuple[bool, Optional[int]]:
        prev = GENESIS_HASH
        for i, entry in enumerate(self._entries):
            payload = entry.get("payload", {})
            expected_hash = hashlib.sha256(_canonical(payload)).hexdigest()
            if entry.get("payload_hash") != expected_hash:
                return False, i
            if entry.get("prev_hash") != prev:
                return False, i
            expected_mac = hmac.new(self.store.key, _canonical(payload), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(str(entry.get("mac", "")), expected_mac):
                return False, i
            prev = entry.get("payload_hash", prev)
        return True, None

    def replay(self) -> Iterator[dict]:
        for entry in self._entries:
            yield entry.get("payload", {})

    def checkpoint(self, path: Optional[str] = None) -> dict:
        """Preserve integrity across compaction: write signed snapshot."""
        target = Path(path) if path else self.path.with_suffix(".checkpoint.json")
        snapshot = {
            "entries": len(self._entries),
            "head": self._entries[-1]["payload_hash"] if self._entries else GENESIS_HASH,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.store.save(str(target), snapshot)
        except Exception:
            pass
        return snapshot

    def __len__(self) -> int:
        return len(self._entries)
