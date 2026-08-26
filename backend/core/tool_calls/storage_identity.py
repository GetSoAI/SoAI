"""SoAI - Tool call storage identity construction [backend/core/tool_calls/storage_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.validation.integers import is_strict_int

__all__ = ("build_tool_call_storage_id_from_fields",)


def build_tool_call_storage_id_from_fields(
    *,
    conv_id: str,
    turn_id: str | None,
    iteration_index: int | None,
    assistant_turn_at_ms: int | None,
    model_variant_index: int | None,
    message_index: int | None,
    call_id: str,
) -> str:
    normalized_conv_id = str(conv_id or "").strip()
    normalized_turn_id = turn_id.strip() if turn_id else ""
    normalized_call_id = str(call_id or "").strip()
    message_index_value = int(message_index) if is_strict_int(message_index) else -1
    assistant_turn_value = int(assistant_turn_at_ms) if is_strict_int(assistant_turn_at_ms) else -1
    model_variant_value = int(model_variant_index) if is_strict_int(model_variant_index) else -1
    iteration_value = int(iteration_index) if is_strict_int(iteration_index) else None
    if normalized_turn_id and iteration_value is not None:
        return (
            f"{normalized_conv_id}:{normalized_turn_id}:{iteration_value}:"
            f"{assistant_turn_value}:{model_variant_value}:{message_index_value}:"
            f"{normalized_call_id}"
        )
    if normalized_turn_id:
        return (
            f"{normalized_conv_id}:{normalized_turn_id}:{assistant_turn_value}:"
            f"{model_variant_value}:{message_index_value}:{normalized_call_id}"
        )
    return (
        f"{normalized_conv_id}:{assistant_turn_value}:{model_variant_value}:"
        f"{message_index_value}:{normalized_call_id}"
    )
