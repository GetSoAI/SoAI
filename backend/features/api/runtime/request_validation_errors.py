"""SoAI - API request validation error extraction [backend/features/api/runtime/request_validation_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi.exceptions import RequestValidationError

__all__ = ("extract_request_validation_message_and_param",)


def _append_location_part(parts: list[str], entry: int | str) -> None:
    if isinstance(entry, int):
        if parts:
            parts[-1] = f"{parts[-1]}[{entry}]"
        else:
            parts.append(f"[{entry}]")
        return
    if isinstance(entry, str) and entry:
        if (
            entry in {"assistant", "user", "system", "developer", "tool"}
            and parts
            and parts[-1].startswith("messages[")
            and parts[-1].endswith("]")
        ):
            return
        parts.append(entry)


def _extract_validation_param(exception: RequestValidationError) -> str | None:
    errors = exception.errors()
    first = errors[0] if errors and isinstance(errors[0], dict) else None
    if first is None:
        return None
    loc_value = first.get("loc")
    if not isinstance(loc_value, list | tuple):
        return None
    parts: list[str] = []
    for entry in loc_value:
        if isinstance(entry, str) and entry in {"body", "query", "path"}:
            continue
        if isinstance(entry, int | str):
            _append_location_part(parts, entry)
    joined = ".".join(parts)
    return joined or None


def _refine_message_role_param(exception: RequestValidationError, param: str | None) -> str | None:
    if not isinstance(param, str):
        return param
    if not (param.startswith("messages[") and param.endswith("]") and param.find(".") == -1):
        return param
    index_text = param.removeprefix("messages[").removesuffix("]")
    if not index_text.isdigit():
        return param
    try:
        body = exception.body
    except AttributeError:
        body = None
    if not isinstance(body, dict):
        return param
    messages_value = body.get("messages")
    if not isinstance(messages_value, list):
        return param
    index = int(index_text)
    if not 0 <= index < len(messages_value):
        return param
    message_value = messages_value[index]
    if isinstance(message_value, dict) and "role" in message_value:
        return f"{param}.role"
    return param


def extract_request_validation_message_and_param(
    exception: RequestValidationError,
) -> tuple[str, str | None]:
    message = "Request validation failed."
    errors = exception.errors()
    first = errors[0] if errors and isinstance(errors[0], dict) else None
    if first is not None:
        msg_value = first.get("msg")
        if isinstance(msg_value, str) and msg_value:
            message = msg_value
    param = _extract_validation_param(exception)
    return (message, _refine_message_role_param(exception, param))
