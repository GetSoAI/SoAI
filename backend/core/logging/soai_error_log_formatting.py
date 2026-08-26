"""SoAI - SoAI error log metadata formatting helpers [backend/core/logging/soai_error_log_formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from collections.abc import Mapping

from core.logging.log_record import SoAILogRecord
from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_soai_error_log_suffix",
    "extract_soai_error_payload",
)

_MAX_ERROR_MESSAGE_LENGTH = 200


def extract_soai_error_payload(record: logging.LogRecord) -> JSONDict | None:
    if not isinstance(record, SoAILogRecord):
        return None
    value = record.soai_error
    if not isinstance(value, Mapping):
        return None
    payload: JSONDict = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str):
            continue
        key = raw_key.strip()
        if not key:
            continue
        payload[key] = raw_value
    return dict(payload) if payload else None


def _sanitize_error_message(value: str) -> str:
    sanitized = value.replace("\n", " ").strip()
    if len(sanitized) <= _MAX_ERROR_MESSAGE_LENGTH:
        return sanitized
    return f"{sanitized[: _MAX_ERROR_MESSAGE_LENGTH - 3]}..."


def build_soai_error_log_suffix(payload: Mapping[str, JSONValue] | None) -> str:
    if not isinstance(payload, Mapping):
        return ""
    parts: list[str] = []
    code = payload.get("code")
    if isinstance(code, str | int) and str(code):
        parts.append(f"code={code}")
    operation = payload.get("operation")
    if isinstance(operation, str) and operation:
        parts.append(f"op={operation}")
    trace_id = payload.get("trace_id")
    if isinstance(trace_id, str) and trace_id:
        parts.append(f"trace_id={trace_id}")
    error_message = payload.get("error_message")
    if isinstance(error_message, str) and error_message:
        parts.append(f"error={_sanitize_error_message(error_message)}")
    return f" | {' '.join(parts)}" if parts else ""
