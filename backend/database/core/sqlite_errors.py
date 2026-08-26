"""SoAI - SQLite error parsing helpers [backend/database/core/sqlite_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
import sqlite3

__all__ = ("parse_sqlite_integrity_error",)

_INTEGRITY_ERROR_UNIQUE_REGEX = r"unique constraint failed:\s*(.+)$"
_INTEGRITY_ERROR_CHECK_REGEX = r"check constraint failed:\s*(.+)$"
_INTEGRITY_ERROR_NOT_NULL_REGEX = r"not null constraint failed:\s*(.+)$"
_TOOL_CALL_SEQUENCE_TRIGGER_MESSAGE = (
    "webui_chat_tool_calls.sequence_index must be contiguous starting at 0"
)


def _normalize_constraint_detail(detail: str | None) -> str | None:
    if not isinstance(detail, str):
        return None
    parts = [part.strip() for part in detail.split(",") if part.strip()]
    if parts:
        return ", ".join(parts)
    stripped = detail.strip()
    return stripped or None


def parse_sqlite_integrity_error(
    exception: sqlite3.IntegrityError,
) -> tuple[str, str | None]:
    error_message = str(exception).lower()

    if "unique constraint failed" in error_message:
        match = re.search(_INTEGRITY_ERROR_UNIQUE_REGEX, str(exception), flags=re.IGNORECASE)
        return ("unique", _normalize_constraint_detail(match.group(1) if match else None))

    if "primary key constraint" in error_message:
        return ("primary_key", None)

    if "foreign key constraint failed" in error_message:
        return ("foreign_key", None)

    if "check constraint failed" in error_message:
        match = re.search(_INTEGRITY_ERROR_CHECK_REGEX, str(exception), flags=re.IGNORECASE)
        return ("check", _normalize_constraint_detail(match.group(1) if match else None))

    if "not null constraint failed" in error_message:
        match = re.search(_INTEGRITY_ERROR_NOT_NULL_REGEX, str(exception), flags=re.IGNORECASE)
        return ("not_null", _normalize_constraint_detail(match.group(1) if match else None))

    if _TOOL_CALL_SEQUENCE_TRIGGER_MESSAGE in error_message:
        return ("trigger", _TOOL_CALL_SEQUENCE_TRIGGER_MESSAGE)

    return ("unknown", None)
