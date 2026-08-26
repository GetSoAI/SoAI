"""SoAI - GPU slot error translation helpers shared across API and hardware subsystems [backend/core/hardware/gpu_slot_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.hardware.gpu_operation_results import gpu_operation_status_code
from core.serialization.json import serialize_json_compact_stable

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("translate_gpu_slot_failure",)


def translate_gpu_slot_failure(
    result: Mapping[str, JSONValue],
) -> tuple[int, str, str, JSONDict]:
    code = str(result.get("code") or "slot_error")
    error_value = result.get("error")
    if isinstance(error_value, dict):
        message = str(
            error_value.get("message") or error_value.get("type") or "GPU slot operation failed.",
        )
    else:
        message = str(error_value) if error_value is not None else "GPU slot operation failed."
    status_code = gpu_operation_status_code(code)
    detail_payload = {
        detail_key: detail_value
        for detail_key, detail_value in result.items()
        if detail_key != "success"
    }
    serialized = None
    if detail_payload:
        try:
            serialized = serialize_json_compact_stable(detail_payload)
        except TypeError:
            serialized = str(detail_payload)
    message_text = f"{message}: {serialized}" if serialized else message
    return (status_code, code, message_text, detail_payload)
