"""SoAI - Streaming log entry shaping helpers [backend/core/logging/handlers/streaming_entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.logging.formatter_support import normalize_component_name, strip_ansi_codes
from core.logging.formatters import UnifiedFormatter
from core.logging.log_record import SoAILogRecord
from core.timing.formatting import timestamp_to_utc_log_format

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_streaming_log_entry",
    "clone_streaming_log_entry",
)


def clone_streaming_log_entry(entry: JSONDict) -> JSONDict:
    return {entry_key: str(entry_value) for entry_key, entry_value in entry.items()}


def _extract_record_trace_id(record: logging.LogRecord) -> str | None:
    record_trace_id = record.trace_id if isinstance(record, SoAILogRecord) else None
    if isinstance(record_trace_id, str) and record_trace_id:
        return record_trace_id
    soai_error_payload = record.soai_error if isinstance(record, SoAILogRecord) else None
    if not isinstance(soai_error_payload, dict):
        return None
    payload_trace_id = soai_error_payload.get("trace_id")
    return payload_trace_id if isinstance(payload_trace_id, str) and payload_trace_id else None


def build_streaming_log_entry(
    record: logging.LogRecord,
    *,
    formatted_text: str,
    logger_name: str,
    formatter: logging.Formatter | None,
) -> JSONDict:
    use_colors = False
    if isinstance(formatter, UnifiedFormatter):
        use_colors = bool(formatter.use_colors)
    clean_text = strip_ansi_codes(formatted_text) if not use_colors else str(formatted_text)
    entry: JSONDict = {
        "timestamp": timestamp_to_utc_log_format(record.created),
        "component": normalize_component_name(logger_name),
        "level": str(record.levelname or "").upper(),
        "message": strip_ansi_codes(record.getMessage()),
        "text": clean_text,
    }
    trace_id_value = _extract_record_trace_id(record)
    if trace_id_value:
        entry["trace_id"] = trace_id_value
    return entry
