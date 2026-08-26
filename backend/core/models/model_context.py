"""SoAI - Model context for provider requests [backend/core/models/model_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.types.json import JSONDict, JSONValue

__all__ = ("ModelContext",)


@dataclass(slots=True)
class ModelContext:
    universal_id: str
    source_model_id: str
    plugin: str
    model_path: str | None = None
    parameters: JSONDict = field(default_factory=dict[str, JSONValue])
    provider_details: JSONDict | None = None
