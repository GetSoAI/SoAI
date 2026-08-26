"""SoAI - Canonical source model identifier helpers [backend/core/models/source_identifier.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ConfigurationError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "require_source_model_id",
    "resolve_source_model_id",
    "write_source_model_id",
)


def resolve_source_model_id(model_data: JSONDict) -> str | None:
    value = model_data.get("source_model_id")
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return None


def require_source_model_id(model_data: JSONDict) -> str:
    source_model_id = resolve_source_model_id(model_data)
    if not source_model_id:
        universal_id = model_data.get("universal_id")
        normalized_universal_id = (
            universal_id.strip()
            if isinstance(universal_id, str) and universal_id.strip()
            else "unknown"
        )
        raise ConfigurationError(
            f"Model '{normalized_universal_id}' is missing source_model_id.",
            details={"universal_id": normalized_universal_id},
        )
    return source_model_id


def write_source_model_id(payload: JSONDict, model_data: JSONDict) -> None:
    payload["source_model_id"] = require_source_model_id(model_data)
