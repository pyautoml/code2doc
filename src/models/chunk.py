#!/usr/bin/env python3

import hashlib
from src.models.document import Document
from pydantic import BaseModel, Field, model_validator


class Chunk(BaseModel):
    content: str
    doc_id: str
    chunk_hash: str
    size: int = Field(default=0)
    metadata: dict = Field(default_factory=dict)

    @classmethod
    @model_validator(mode="before")
    def chunk_size(cls, values: dict) -> dict:
        content = values.get("content", "")
        values["size"] = len(content)
        return values

    @classmethod
    def from_document(cls, doc: Document, content: str, chunk_num: int):
        return cls(
            content=content,
            doc_id=doc.doc_uuid,
            chunk_hash=hashlib.md5(content.encode()).hexdigest(),
            metadata={
                "source_file": str(doc.file_path),
                "chunk_num": chunk_num,
                "repo": doc.repo_name,
            },
        )
