"""SoAI - Shared tool-call error payload helpers [backend/core/tool_calls/error_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.messages import resolve_error_message

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "TOOL_CALL_USER_DENIED_ERROR_CODE",
    "TOOL_CALL_USER_DENIED_ERROR_MESSAGE",
    "build_tool_call_error_payload",
)

TOOL_CALL_USER_DENIED_ERROR_CODE = "user_denied"
TOOL_CALL_USER_DENIED_ERROR_MESSAGE = "Tool call denied by the user."


def build_tool_call_error_payload(
    *,
    error_message: str,
    code: str | int,
    data: JSONValue | None = None,
) -> JSONDict:
    payload: JSONDict = {
        "error": resolve_error_message(error_message, default_message="Tool call failed."),
        "code": code,
    }
    if data is not None:
        payload["data"] = data
    return payload
