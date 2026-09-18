"""Secrets-manager abstraction (v1.1 W3).

Default is env-based; file, chained, AWS and Vault providers available.
Keys are never persisted, logged, or included in traces.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Protocol

from ..config import _load_env_file


def redact(value: str) -> str:
    return "***"


class SecretsProvider(Protocol):
    def get(self, name: str) -> Optional[str]: ...
    def require(self, name: str) -> str: ...
    def list_available(self) -> list[str]: ...


class EnvSecretsProvider:
    """Default provider; wraps hardened .env loader + os.environ."""

    def __init__(self) -> None:
        _load_env_file()

    def get(self, name: str) -> Optional[str]:
        if not name:
            return None
        return os.environ.get(name)

    def require(self, name: str) -> str:
        value = self.get(name)
        if not value:
            raise KeyError(f"Missing required secret: {name}")
        return value

    def list_available(self) -> list[str]:
        return [k for k, v in os.environ.items() if v]


class FileSecretsProvider:
    """JSON/YAML keyfile provider: {"KEY": "value"}."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._data: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            text = self.path.read_text(encoding="utf-8")
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                import yaml  # lazy; pyyaml is a core dep

                data = yaml.safe_load(text)
            if isinstance(data, dict):
                self._data = {str(k): str(v) for k, v in data.items()}
        except Exception:
            self._data = {}

    def get(self, name: str) -> Optional[str]:
        return self._data.get(name)

    def require(self, name: str) -> str:
        value = self.get(name)
        if not value:
            raise KeyError(f"Missing required secret: {name}")
        return value

    def list_available(self) -> list[str]:
        return list(self._data.keys())


class ChainedSecretsProvider:
    """First hit wins across ordered providers."""

    def __init__(self, providers: list):
        self.providers = providers

    def get(self, name: str) -> Optional[str]:
        for p in self.providers:
            try:
                value = p.get(name)
            except Exception:
                continue
            if value:
                return value
        return None

    def require(self, name: str) -> str:
        value = self.get(name)
        if not value:
            raise KeyError(f"Missing required secret: {name}")
        return value

    def list_available(self) -> List[str]:
        seen: List[str] = []
        for p in self.providers:
            try:
                for k in p.list_available():
                    if k not in seen:
                        seen.append(k)
            except Exception:
                continue
        return seen


class AwsSecretsManagerProvider:
    """Lazy boto3 provider behind the [secrets] extra."""

    def __init__(self, region: Optional[str] = None):
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import boto3  # type: ignore
            except ImportError as exc:
                raise ImportError(
                    "AwsSecretsManagerProvider requires the [secrets] extra: pip install modelhop[secrets]"
                ) from exc
            self._client = boto3.client("secretsmanager", region_name=self.region)
        return self._client

    def get(self, name: str) -> Optional[str]:
        try:
            resp = self._get_client().get_secret_value(SecretId=name)
            return resp.get("SecretString")
        except Exception:
            return None

    def require(self, name: str) -> str:
        value = self.get(name)
        if not value:
            raise KeyError(f"Missing required secret: {name}")
        return value

    def list_available(self) -> list[str]:
        return []


class VaultSecretsProvider:
    """Lazy hvac provider behind the [secrets] extra."""

    def __init__(self, url: Optional[str] = None, token: Optional[str] = None):
        self.url = url or os.environ.get("VAULT_ADDR", "")
        self.token = token or os.environ.get("VAULT_TOKEN", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import hvac  # type: ignore
            except ImportError as exc:
                raise ImportError(
                    "VaultSecretsProvider requires the [secrets] extra: pip install modelhop[secrets]"
                ) from exc
            self._client = hvac.Client(url=self.url, token=self.token)
        return self._client

    def get(self, name: str) -> Optional[str]:
        try:
            client = self._get_client()
            # Support "mount/path:key" or plain path.
            if ":" in name:
                path, key = name.split(":", 1)
            else:
                path, key = name, "value"
            resp = client.secrets.kv.v2.read_secret_version(path=path)
            data = resp.get("data", {}).get("data", {})
            value = data.get(key)
            return str(value) if value is not None else None
        except Exception:
            return None

    def require(self, name: str) -> str:
        value = self.get(name)
        if not value:
            raise KeyError(f"Missing required secret: {name}")
        return value

    def list_available(self) -> list[str]:
        return []
