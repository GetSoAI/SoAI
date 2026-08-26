"""SoAI - Plugin manager command handlers [backend/plugins/manager/commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.errors.status_mapping import error_type_to_status_code
from core.events.types_base import Event
from core.state.command_results import normalize_command_result
from plugins.action_response import PluginActionResponse

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("translate_command_result",)


def translate_command_result(
    result: JSONValue | Event,
    *,
    success_status: int,
) -> PluginActionResponse:
    view = normalize_command_result(result)
    if view.result_type == "error":
        error_type = view.error_type or ErrorType.SERVER_ERROR
        return PluginActionResponse(
            success=False,
            status_code=error_type_to_status_code(error_type),
            error_type=error_type.value,
            error_message=view.message,
        )
    if view.result_type == "task" and view.success is False:
        return PluginActionResponse(
            success=False,
            status_code=400,
            error_type="action_failed",
            error_message=view.message,
        )
    payload = view.payload if isinstance(view.payload, dict) else None
    return PluginActionResponse(success=True, status_code=success_status, payload=payload)
