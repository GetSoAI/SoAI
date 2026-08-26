"""SoAI - Shared activity payload builders for realtime UI streams [backend/core/activity_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NotRequired, TypedDict

from core.types.json import JSONDict
from core.types.json_value import filter_json_mapping_strict
from core.validation.strings import coerce_optional_trimmed_str

__all__ = ("build_activity_payload",)


class _ActivityPayloadFields(TypedDict):
    status: str
    started_at_ms: int
    duration_ms: int
    reason: NotRequired[str]
    error_type: NotRequired[str]


def build_activity_payload(
    *,
    status: str,
    started_at_ms: int,
    duration_ms: int,
    reason: str | None,
    error_type: str | None,
) -> JSONDict:
    payload: _ActivityPayloadFields = {
        "status": status,
        "started_at_ms": max(0, int(started_at_ms)),
        "duration_ms": max(0, int(duration_ms)),
    }
    normalized_reason = coerce_optional_trimmed_str(reason)
    if normalized_reason is not None:
        payload["reason"] = normalized_reason
    normalized_error_type = coerce_optional_trimmed_str(error_type)
    if normalized_error_type is not None:
        payload["error_type"] = normalized_error_type
    return filter_json_mapping_strict(
        payload,
        error_message="Activity payload must be JSON-compatible.",
    )
