from pathlib import Path
from typing import List, Optional

import yaml

from ..core.models import HubConfig

COMMUNITY_CONFIGS_PATH = Path(__file__).parent.parent.parent / "data" / "community_configs"


class Hub:
    def __init__(self):
        self.configs_path = COMMUNITY_CONFIGS_PATH

    def list_configs(self) -> List[HubConfig]:
        configs = []
        if not self.configs_path.exists():
            return configs

        for config_file in self.configs_path.glob("*.yaml"):
            try:
                with open(config_file, "r") as f:
                    data = yaml.safe_load(f)
                    f.read() if f.readable() else ""

                configs.append(
                    HubConfig(
                        name=data.get("name", config_file.stem),
                        author=data.get("author", "ModelHop Community"),
                        description=data.get("description", f"Config: {config_file.stem}"),
                        rating=data.get("rating", 4.5),
                        downloads=data.get("downloads", 100),
                        tags=data.get("tags", []),
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

        with open(destination, "w") as f:
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
