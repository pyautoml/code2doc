#!/usr/bin/env python3

from typing import Optional
from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    doc_type: str
    file_size: Optional[int] = None  # Size in bytes
    last_modified: Optional[float] = None
