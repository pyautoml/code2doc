#!/usr/bin/env python3
import toml
from pathlib import Path
from typing import Dict, Any


class ConfigLoader:
    def __init__(self, base_dir: Path = Path(__file__).parent.parent.parent) -> None:
        self.base_dir: Path = base_dir
        self.configs: dict = self._load_toml("config/settings.toml")
        self.secrets: dict = self._load_toml("config/secrets.toml")

    def _load_toml(self, rel_path: str) -> Dict[str, Any]:
        with open(self.base_dir / rel_path, "r", encoding="utf-8") as f:
            return toml.load(f)

    def get(self, key: str, default=None) -> Any:
        keys = key.split(".")
        val = self.configs
        for k in keys:
            val = val.get(k, {})
        return val if val != {} else default

    def get_secret(self, key: str, default=None) -> Any:
        keys = key.split(".")
        val = self.secrets
        for k in keys:
            val = val.get(k, {})
        return val if val != {} else default
