#!/usr/bin/env python3

import os
import psutil
import logging
from enum import Enum
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass


logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


class FileSize(Enum):
    SMALL = "small"         # < 1MB
    MEDIUM = "medium"       # 1MB - 50MB
    LARGE = "large"         # 50MB - 500MB
    EXTRA_LARGE = "xlarge"  # > 500MB


@dataclass
class FileClassification:
    path: Path
    size_bytes: int
    size_category: FileSize
    estimated_chunks: int
    memory_requirement_mb: float


class AdaptiveFileClassifier:

    def __init__(self, chunk_size: int = 2000):
        self.chunk_size = chunk_size
        self.available_memory_gb = psutil.virtual_memory().available / (1024**3)
        self.safe_memory_threshold = self.available_memory_gb * 0.7  # Use 70% of available memory

        logger.info(
            f"Available memory: {self.available_memory_gb:.2f}GB, "
            f"Safe threshold: {self.safe_memory_threshold:.2f}GB"
        )

    def classify_files(
        self, file_paths: List[Path]
    ) -> Dict[FileSize, List[FileClassification]]:
        classifications = {size: [] for size in FileSize}

        for path in file_paths:
            if not path.is_file():
                continue

            size_bytes = path.stat().st_size
            size_category = self._get_size_category(size_bytes)
            estimated_chunks = max(1, size_bytes // self.chunk_size)
            memory_requirement_mb = (size_bytes * 3) / (1024**2)

            classification = FileClassification(
                path=path,
                size_bytes=size_bytes,
                size_category=size_category,
                estimated_chunks=estimated_chunks,
                memory_requirement_mb=memory_requirement_mb,
            )

            classifications[size_category].append(classification)

        for size_cat, files in classifications.items():
            if files:
                total_size = sum(f.size_bytes for f in files) / (1024**2)
                logger.info(
                    f"{size_cat.value.upper()}: {len(files)} files, {total_size:.1f}MB total"
                )

        return classifications

    @staticmethod
    def _get_size_category(size_bytes: int) -> FileSize:
        size_mb = size_bytes / (1024**2)
        if size_mb < 1:
            return FileSize.SMALL
        elif size_mb < 50:
            return FileSize.MEDIUM
        elif size_mb < 500:
            return FileSize.LARGE
        else:
            return FileSize.EXTRA_LARGE

    def can_process_together(self, files: List[FileClassification]) -> bool:
        total_memory_mb = sum(f.memory_requirement_mb for f in files)
        return total_memory_mb < (self.safe_memory_threshold * 1024)
