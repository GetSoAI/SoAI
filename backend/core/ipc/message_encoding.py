"""SoAI - IPC message encoding and size enforcement [backend/core/ipc/message_encoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exceptions import PayloadTooLargeError, ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict, JSONValue

__all__ = ("encode_ipc_message_bytes",)


def encode_ipc_message_bytes(
    message: JSONDict,
    *,
    max_bytes: int,
    details: Mapping[str, JSONValue] | None = None,
    operation: str | None = None,
) -> bytes:
    if not isinstance(message, dict):
        raise ValidationError("IPC message must be a JSON object.")
    payload = serialize_json_compact_stable_strict(message, ensure_ascii=False)
    data = (f"{payload}\n").encode("utf-8", errors="strict")
    if len(data) > int(max_bytes):
        raise PayloadTooLargeError(
            "IPC encoded message exceeds maximum size.",
            details={
                "actual_bytes": len(data),
                "max_bytes": int(max_bytes),
                **(dict(details) if details is not None else {}),
            },
            operation=operation,
        )
    return data
