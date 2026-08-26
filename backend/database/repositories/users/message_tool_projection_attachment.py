"""SoAI - Message tool projection attachment [backend/database/repositories/users/message_tool_projection_attachment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from database.repositories.users.tool_call_row_mapping import (
    format_preview_tool_call_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRow

__all__ = ("attach_tool_call_projections",)


def attach_tool_call_projections(messages: list[JSONDict], tool_rows: Sequence[SQLiteRow]) -> None:
    projections_by_assistant_at_ms: dict[int, list[JSONDict]] = {}
    for row in tool_rows:
        formatted = format_preview_tool_call_row(row)
        if formatted is None:
            continue
        assistant_at_ms_value = formatted.get("assistant_at_ms")
        if not is_strict_int(assistant_at_ms_value):
            continue
        projections = projections_by_assistant_at_ms.get(assistant_at_ms_value)
        if projections is None:
            projections_by_assistant_at_ms[assistant_at_ms_value] = [formatted]
        else:
            projections.append(formatted)
    for message in messages:
        if message.get("role") != "assistant":
            continue
        timestamp_value = message.get("timestamp")
        if not is_strict_int(timestamp_value):
            continue
        projections = projections_by_assistant_at_ms.get(
            timestamp_value,
            [],
        )
        message["tool_call_projections"] = projections
