"""SoAI - Chroma collection naming utilities [backend/mcp/storage/chroma_naming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.errors.exceptions import ValidationError

__all__ = (
    "build_reindex_collection_name",
    "collection_prefix_from_conv_id",
)

_SAFE_NAME_PATTERN = r"[^A-Za-z0-9_]+"


def collection_prefix_from_conv_id(conv_id: str) -> str:
    normalized = str(conv_id or "").strip()
    if not normalized:
        raise ValidationError("conv_id is required for collection naming.")
    base_id = normalized.removeprefix("conv_")
    safe = re.sub(_SAFE_NAME_PATTERN, "_", base_id.replace("-", "_")).strip("_")
    if not safe:
        raise ValidationError("conv_id cannot be normalized into a valid collection prefix.")
    return f"conv_{safe}"


def build_reindex_collection_name(conv_id: str, task_id: str) -> str:
    prefix = collection_prefix_from_conv_id(conv_id)
    normalized_task_id = str(task_id or "").strip()
    if not normalized_task_id:
        raise ValidationError("task_id is required for reindex collection naming.")
    task_safe = re.sub(_SAFE_NAME_PATTERN, "_", normalized_task_id).strip("_")
    if not task_safe:
        raise ValidationError("task_id cannot be normalized into a valid collection name suffix.")
    return f"{prefix}_reindex_{task_safe}"
