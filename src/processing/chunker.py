#!/usr/bin/env python3

import mmap
from typing import Generator
from src.models.chunk import Chunk
from src.models.document import Document
from src.core.configuration import ConfigLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


class ChunkGenerator:

    def __init__(self):
        self.config: ConfigLoader = ConfigLoader()
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.get("processing.chunk_size", 2000),
            chunk_overlap=self.config.get("processing.chunk_overlap", 200),
            length_function=len,
        )

    def process(self, document: Document) -> Generator[Chunk, None, None]:
        file_path = document.file_path
        if file_path.stat().st_size > self.config.get(
            "processing.large_file_threshold", 10_000_000
        ):
            yield from self._stream_chunks(document)
        else:
            yield from self._batch_chunks(document)

    def _stream_chunks(self, document: Document) -> Generator[Chunk, None, None]:
        buffer = ""
        chunk_num = 0
        file_path = document.file_path

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                for line in iter(mm.readline, b""):
                    try:
                        decoded_line = line.decode("utf-8")
                    except UnicodeDecodeError:
                        decoded_line = line.decode("latin-1")

                    buffer += decoded_line

                    if len(buffer) >= self.config.get("processing.chunk_size", 2000) * 2:
                        for chunk_text in self.splitter.split_text(buffer):
                            yield Chunk.from_document(
                                doc=document, content=chunk_text, chunk_num=chunk_num
                            )
                            chunk_num += 1
                        buffer = ""
                if buffer:
                    for chunk_text in self.splitter.split_text(buffer):
                        yield Chunk.from_document(
                            doc=document, content=chunk_text, chunk_num=chunk_num
                        )
                        chunk_num += 1

    def _batch_chunks(self, document: Document) -> Generator[Chunk, None, None]:
        try:
            with open(document.file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            for i, chunk_text in enumerate(self.splitter.split_text(content)):
                yield Chunk.from_document(doc=document, content=chunk_text, chunk_num=i)

        except MemoryError:
            yield from self._stream_chunks(document)
