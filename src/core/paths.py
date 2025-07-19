#!/usr/bin/env python3
import platform
from pathlib import Path


class PathManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def resolve(self, rel_path: str) -> Path:
        path = (self.base_dir / rel_path).resolve()
        if platform.system() == "Windows":
            path = Path(str(path).replace("/", "\\"))
        return path

    def create_dir(self, rel_path: str) -> Path:
        path = self.resolve(rel_path)
        path.mkdir(parents=True, exist_ok=True)
        return path
