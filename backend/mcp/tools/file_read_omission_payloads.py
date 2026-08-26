"""SoAI - MCP read_file omitted content payloads [backend/mcp/tools/file_read_omission_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable_strict
from mcp.tools.file_content_classification import (
    FileReadContentClassification,
    classify_read_file_sample,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_binary_omitted_payload",
    "build_oversize_omitted_payload",
)


def _base_omitted_payload(
    *,
    path: str,
    mode: str,
    offset: int,
    limit: int,
    truncated: bool,
    truncation_reason: str | None,
    classification: FileReadContentClassification,
    content_omitted_reason: str,
) -> JSONDict:
    payload: JSONDict = {
        "path": path,
        "mode": mode,
        "offset": offset,
        "limit": limit,
        "total_lines": 0,
        "returned_lines": 0,
        "start_line": None,
        "end_line": None,
        "next_offset": None,
        "truncated": truncated,
        "truncation_reason": truncation_reason,
        "content_truncated": False,
        "serialized_response_chars": 0,
        "max_serialized_response_chars": None,
        "content": "",
        "rendered_as_text": False,
        "content_omitted": True,
        "content_omitted_reason": content_omitted_reason,
        "mime_type": classification.mime_type,
        "size_bytes": classification.size_bytes,
    }
    if not classification.text_safe:
        payload["binary"] = True
    payload["serialized_response_chars"] = len(
        serialize_json_compact_stable_strict(payload, ensure_ascii=False),
    )
    return payload


def build_binary_omitted_payload(
    *,
    path: str,
    mode: str,
    offset: int,
    limit: int,
    classification: FileReadContentClassification,
) -> JSONDict:
    return _base_omitted_payload(
        path=path,
        mode=mode,
        offset=offset,
        limit=limit,
        truncated=False,
        truncation_reason=None,
        classification=classification,
        content_omitted_reason="binary_file",
    )


def build_oversize_omitted_payload(
    *,
    path: str,
    mode: str,
    offset: int,
    limit: int,
    sample: bytes,
    size_bytes: int,
    max_size_bytes: int,
) -> JSONDict:
    classification = classify_read_file_sample(
        path=path,
        sample=sample,
        size_bytes=size_bytes,
    )
    payload = _base_omitted_payload(
        path=path,
        mode=mode,
        offset=offset,
        limit=limit,
        truncated=True,
        truncation_reason="source_size",
        classification=classification,
        content_omitted_reason="source_size_limit",
    )
    payload["max_size_bytes"] = max_size_bytes
    payload["serialized_response_chars"] = len(
        serialize_json_compact_stable_strict(payload, ensure_ascii=False),
    )
    return payload
