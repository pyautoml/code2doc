#!/usr/bin/env python3

from typing import List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator


class Embedding(BaseModel):
    vector: List[float]
    chunk_id: str = Field(..., description="Format: <doc_id>:<chunk_hash>")
    model_name: str = Field(default="nomic-embed-text")
    size: int = Field(default=0)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    @classmethod
    @model_validator(mode="before")
    def validate_and_convert_vector(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(values, dict):
            vector = values.get("vector")
            if vector is not None:
                if hasattr(vector, "tolist"):
                    vector = vector.tolist()
                elif not isinstance(vector, list):
                    vector = list(vector) if vector else []
                try:
                    vector = [float(x) for x in vector]
                    values["vector"] = vector
                    values["size"] = len(vector)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid vector data: {e}")
            else:
                values["size"] = 0
        return values
