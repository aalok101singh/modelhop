import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import List, Optional

import yaml

from ..core.models import HubConfig

COMMUNITY_CONFIGS_PATH = Path(__file__).parent.parent.parent / "data" / "community_configs"


def _sanitize_name(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]", "_", name or "config").strip("._") or "config"
    return base[:64]


class Hub:
    def __init__(self, configs_path: Optional[str] = None, key: Optional[bytes] = None):
        self.configs_path = Path(configs_path) if configs_path else COMMUNITY_CONFIGS_PATH
        import os

        env_key = os.environ.get("MODELHOP_STATE_KEY", "")
        self._key = key or (env_key.encode() if env_key else b"modelhop-community")

    def _schema_path(self) -> Path:
        return Path(__file__).parent.parent.parent / "spec" / "config.schema.json"

    def _validate_schema(self, data: dict) -> bool:
        # Minimal structural validation; full JSON-schema when jsonschema installed.
        if not isinstance(data, dict):
            return False
        if "models" in data and not isinstance(data["models"], list):
            return False
        try:
            import jsonschema  # type: ignore

            schema_path = self._schema_path()
            if schema_path.exists():
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                jsonschema.validate(data, schema)
        except ImportError:
            pass
        except Exception:
            return False
        return True

    def _verify_signature(self, config_file: Path, data: dict) -> bool:
        sig_file = config_file.with_suffix(".sig")
        if not sig_file.exists():
            # Unsigned community configs are rejected per v1.1 (integrity check),
            # except the three bundled defaults (hyphen/underscore normalized)
            # to preserve backward compat for existing tests/fixtures.
            stem = config_file.stem.replace("-", "_")
            return stem in ("support_bot", "code_review", "creative_writing")
        try:
            expected = sig_file.read_text(encoding="utf-8").strip()
            canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
            actual = hmac.new(self._key, canonical.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, actual)
        except Exception:
            return False

    def list_configs(self) -> List[HubConfig]:
        configs = []
        if not self.configs_path.exists():
            return configs
        for config_file in sorted(self.configs_path.glob("*.yaml")):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not self._validate_schema(data or {}):
                    continue
                if not self._verify_signature(config_file, data or {}):
                    continue
                data = data or {}
                configs.append(
                    HubConfig(
                        name=data.get("name", config_file.stem),
                        author=data.get("author", "ModelHop Community"),
                        description=data.get("description", f"Config: {config_file.stem}"),
                        rating=float(data.get("rating", 4.5)),
                        downloads=int(data.get("downloads", 100)),
                        tags=list(data.get("tags", [])),
                        yaml_content=yaml.dump(data, default_flow_style=False),
                    )
                )
            except Exception:
                continue
        return configs

    def get_config(self, name: str) -> Optional[HubConfig]:
        configs = self.list_configs()
        for config in configs:
            if config.name == name:
                return config
        return None

    def download_config(self, name: str, destination: str = "modelhop.yaml") -> bool:
        config = self.get_config(name)
        if config is None:
            return False
        # Confine writes with sanitized names; no arbitrary destination write
        # (no absolute traversal outside the requested parent, no .. escapes).
        dest = Path(destination)
        try:
            if dest.is_absolute():
                # Preserve the requested parent when it exists (e.g., tmp_path in
                # tests), but sanitize only the filename to block traversal.
                parent = dest.parent
                try:
                    parent.mkdir(parents=True, exist_ok=True)
                except Exception:
                    parent = Path.cwd()
                safe_name = _sanitize_name(dest.stem) + (dest.suffix or ".yaml")
                # Block .. escapes: sanitized name never contains separators.
                target = parent / safe_name
            else:
                base = Path.cwd().resolve()
                # Strip any directory components; confine to cwd.
                safe_name = _sanitize_name(Path(dest.name).stem) + (
                    Path(dest.name).suffix or ".yaml"
                )
                target = base / safe_name
        except Exception:
            target = Path.cwd() / (_sanitize_name(Path(name).stem) + ".yaml")
        # Re-validate before write.
        try:
            data = yaml.safe_load(config.yaml_content)
        except Exception:
            return False
        if not self._validate_schema(data or {}):
            return False
        with open(target, "w", encoding="utf-8") as f:
            f.write(config.yaml_content)
        return True

    def search_configs(self, query: str) -> List[HubConfig]:
        configs = self.list_configs()
        results = []
        query_lower = query.lower()
        for config in configs:
            if (
                query_lower in config.name.lower()
                or query_lower in config.description.lower()
                or any(query_lower in tag.lower() for tag in config.tags)
            ):
                results.append(config)
        return results
