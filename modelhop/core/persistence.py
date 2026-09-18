import hashlib
import hmac
import json
import os
import secrets
import tempfile
from pathlib import Path
from typing import Optional


class StateIntegrityError(Exception):
    """Raised when signed state fails integrity verification."""


def _default_key_path() -> Path:
    return Path.home() / ".modelhop" / "state.key"


def _resolve_key(explicit: Optional[bytes] = None) -> bytes:
    if explicit is not None:
        return explicit
    env_key = os.environ.get("MODELHOP_STATE_KEY", "")
    if env_key:
        return env_key.encode("utf-8")
    key_path = _default_key_path()
    if key_path.exists():
        try:
            return key_path.read_bytes().strip()
        except OSError:
            pass
    # Generate and persist with user-only permissions.
    key_path.parent.mkdir(parents=True, exist_ok=True)
    new_key = secrets.token_bytes(32)
    try:
        fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, new_key)
        finally:
            os.close(fd)
        try:
            if os.name == "posix":
                os.chmod(key_path, 0o600)
        except OSError:
            pass
    except OSError:
        pass
    return new_key


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


class SignedStore:
    """HMAC-SHA256 signed JSON store.

    Envelope: {"schema_version", "alg": "hmac-sha256", "mac", "payload"}.
    MAC is computed over canonical JSON of the payload.
    """

    def __init__(self, key: Optional[bytes] = None, schema_version: int = 1):
        self.key = _resolve_key(key)
        self.schema_version = schema_version

    def _mac(self, payload: dict) -> str:
        return hmac.new(self.key, _canonical(payload), hashlib.sha256).hexdigest()

    def save(self, path: str, payload: dict) -> None:
        envelope = {
            "schema_version": self.schema_version,
            "alg": "hmac-sha256",
            "mac": self._mac(payload),
            "payload": payload,
        }
        atomic_write_json(path, envelope)

    def load(self, path: str) -> dict:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                envelope = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise StateIntegrityError(f"Unreadable state file {path}: {exc}") from exc
        # Legacy unsigned store: structurally validated, then caller re-signs.
        if "payload" not in envelope or "mac" not in envelope:
            if not isinstance(envelope, dict):
                raise StateIntegrityError(f"Invalid state structure in {path}")
            return envelope
        payload = envelope.get("payload", {})
        expected = self._mac(payload)
        actual = envelope.get("mac", "")
        if not hmac.compare_digest(str(expected), str(actual)):
            raise StateIntegrityError(f"MAC mismatch for {path}: possible tampering")
        return payload


def atomic_write_json(path: str, data: dict) -> None:
    """Write JSON atomically: write to a temp file, then os.replace.

    Guarantees readers never observe a partially written / empty file even
    if the process is killed mid-write.
    """
    directory = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
