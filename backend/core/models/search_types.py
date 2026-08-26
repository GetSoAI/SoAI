"""SoAI - Core remote model search types [backend/core/models/search_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel

__all__ = (
    "RemoteModelSearchResultBaseModel",
    "RemoteModelSearchVariantBaseModel",
)


class RemoteModelSearchResultBaseModel(BaseModel):
    id: str
    name: str
    source: str
    summary: str | None = None
    score: float | None = None


class RemoteModelSearchVariantBaseModel(BaseModel):
    id: str
    name: str
    uri: str
    size_bytes: int | None = None
    quantization: str | None = None
    checksum: str | None = None
