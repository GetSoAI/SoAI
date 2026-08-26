"""SoAI - Tool-result omission payload helpers [backend/core/tool_calls/tool_result_omission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.tool_calls.tool_result_prompt_primitives import safe_json_dumps

__all__ = ("build_tool_result_omission_stub_json",)


def build_tool_result_omission_stub_json(*, tool_call_id: str, tool_name: str) -> str:
    return safe_json_dumps(
        {
            "__soai_tool_result_omitted__": True,
            "reason": "tool_result_prompt_budget_exceeded",
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
        },
    ).strip()
