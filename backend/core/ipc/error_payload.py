"""SoAI - Structured error payloads for trusted IPC peers [backend/core/ipc/error_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.errors.exceptions import SoAIError
    from core.types.json import JSONDict

__all__ = ("build_ipc_error_payload",)


def build_ipc_error_payload(error: SoAIError) -> JSONDict:
    payload: JSONDict = {
        "code": error.code,
        "message": error.message,
    }
    if error.details:
        payload["details"] = dict(error.details)
    if error.trace_id:
        payload["trace_id"] = error.trace_id
    return payload
