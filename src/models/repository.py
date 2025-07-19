#!/usr/bin/env python3

from pydantic import BaseModel, Field


class RepositorySource(BaseModel):
    source: str = Field(..., description="The source URL or path of the repository")
    type: str = Field(default="online", description="Types: online, local")
