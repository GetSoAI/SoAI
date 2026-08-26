"""SoAI - Error message normalization helpers [backend/core/errors/messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "resolve_error_message",
    "resolve_exception_error_message",
)


def resolve_error_message(message: str, *, default_message: str) -> str:
    resolved_message = message.strip()
    if resolved_message:
        return resolved_message
    return default_message


def resolve_exception_error_message(exception: BaseException) -> str:
    exception_message = str(exception).strip()
    exception_name = type(exception).__name__
    if exception_message:
        return f"{exception_name}: {exception_message}"
    return exception_name
