"""SoAI - Remote model search types [backend/core/models/remote_model_search_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.models.remote_model_search_error import RemoteModelSearchError
from core.types.json import JSONDict, JSONValue

__all__ = (
    "HuggingFaceReference",
    "RemoteModelSearchError",
    "RemoteModelSearchResult",
    "RemoteModelSearchVariant",
)


@dataclass(frozen=True, slots=True)
class RemoteModelSearchVariant:
    id: str
    name: str
    uri: str
    size_bytes: int | None = None
    quantization: str = ""
    checksum: str = ""
    extra: JSONDict = field(default_factory=dict[str, JSONValue])


@dataclass(frozen=True, slots=True)
class RemoteModelSearchResult:
    id: str
    name: str
    source: str
    summary: str = ""
    score: int | None = None
    tags: list[str] = field(default_factory=list[str])
    metadata: JSONDict = field(default_factory=dict[str, JSONValue])
    variants: list[RemoteModelSearchVariant] = field(default_factory=list[RemoteModelSearchVariant])


@dataclass(frozen=True, slots=True)
class HuggingFaceReference:
    repo_id: str
    file_path: str | None
    segments: tuple[str, ...]

    @property
    def has_file(self) -> bool:
        return bool(self.file_path)
