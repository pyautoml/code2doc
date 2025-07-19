#!/usr/bin/env python3

import hashlib
from uuid import uuid4
from pathlib import Path
from typing import Optional
from src.models.document_metadata import DocumentMetadata
from pydantic import BaseModel, Field, ConfigDict


class Document(BaseModel):
    doc_uuid: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    file_path: Path
    file_hash: str
    repo_name: str
    metadata: Optional[DocumentMetadata] = Field(default=None)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        str_strip_whitespace=True,
        frozen=True,
    )

    @classmethod
    def create(
        cls,
        content: str,
        file_path: Path,
        repo_name: str,
        metadata: Optional[DocumentMetadata] = None,
    ):
        file_hash = hashlib.md5(content.encode()).hexdigest()
        return cls(
            content=content,
            file_path=file_path,
            file_hash=file_hash,
            repo_name=repo_name,
            metadata=metadata,
        )

    @classmethod
    def from_file(cls, path: Path, repo_name: str, metadata: DocumentMetadata):
        if not path.is_file():
            raise ValueError(f"Path {path} is not a valid file.")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="latin1")
            except Exception as e:
                raise ValueError(f"Could not read file {path}: {e}")

        return cls.create(
            content=content, file_path=path, repo_name=repo_name, metadata=metadata
        )
