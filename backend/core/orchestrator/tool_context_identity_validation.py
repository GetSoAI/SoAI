"""SoAI - MCP tool context identity validation helpers [backend/core/orchestrator/tool_context_identity_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("build_tool_context_message_index_mismatch_message",)


def build_tool_context_message_index_mismatch_message(
    *,
    surface: str,
    conv_id: str,
    assistant_at_ms: int,
    tool_context_message_index: int,
    runtime_message_index: int,
) -> str:
    normalized_surface = str(surface or "").strip() or "Surface"
    normalized_conv_id = str(conv_id or "").strip() or "unknown"
    return (
        f"{normalized_surface} tool context message_index does not match the assistant runtime message_index "
        f"(conv_id={normalized_conv_id}, assistant_at_ms={int(assistant_at_ms)}, "
        f"tool_context.message_index={int(tool_context_message_index)}, runtime.message_index={int(runtime_message_index)})."
    )
