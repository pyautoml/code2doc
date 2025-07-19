#!/usr/bin/env python3

import os
import mmap
import logging
from pathlib import Path
from typing import Iterator, Optional


logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


class StreamingFileReader:

    def __init__(self, chunk_size_mb: int = 10):
        self.chunk_size_bytes = chunk_size_mb * 1024 * 1024

    def read_file_chunks(
        self, file_path: Path, encoding: str = "utf-8"
    ) -> Iterator[str]:
        try:
            with open(file_path, "r", encoding=encoding) as file:
                while True:
                    chunk = file.read(self.chunk_size_bytes)
                    if not chunk:
                        break
                    yield chunk
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="latin1") as file:
                    while True:
                        chunk = file.read(self.chunk_size_bytes)
                        if not chunk:
                            break
                        yield chunk
            except Exception as e:
                logger.error(f"Could not read file {file_path}: {e}")
                return

    @staticmethod
    def read_file_with_mmap(file_path: Path) -> Optional[str]:
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                with mmap.mmap(
                    file.fileno(), 0, access=mmap.ACCESS_READ
                ) as mapped_file:
                    return mapped_file.read().decode("utf-8")
        except Exception as e:
            logger.error(f"Memory mapping failed for {file_path}: {e}")
            return None
