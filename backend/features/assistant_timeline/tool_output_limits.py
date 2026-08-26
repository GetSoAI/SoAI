"""SoAI - Shared assistant timeline tool output limit helpers [backend/features/assistant_timeline/tool_output_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("MAX_TOOL_OUTPUT_CHARS", "append_capped_tool_output")

MAX_TOOL_OUTPUT_CHARS: int = 2_000_000


def append_capped_tool_output(base_output: str, delta: str) -> str:
    next_output = f"{base_output}{delta}"
    if len(next_output) <= MAX_TOOL_OUTPUT_CHARS:
        return next_output
    return next_output[len(next_output) - MAX_TOOL_OUTPUT_CHARS :]
