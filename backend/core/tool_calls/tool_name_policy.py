"""SoAI - Tool call name normalization and live result policy [backend/core/tool_calls/tool_name_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "normalize_tool_leaf_name",
    "tool_call_running_result_is_detail_hydrated",
)

_DETAIL_HYDRATED_RUNNING_RESULT_TOOL_NAMES: frozenset[str] = frozenset(
    {"shell", "shell_write_stdin", "subagent_spawn", "read_video", "hardware_benchmark"},
)


def normalize_tool_leaf_name(tool_name: str) -> str:
    normalized_tool_name = "_".join(tool_name.strip().lower().split())
    return normalized_tool_name.rsplit(".", 1)[-1]


def tool_call_running_result_is_detail_hydrated(tool_name: str) -> bool:
    return normalize_tool_leaf_name(tool_name) in _DETAIL_HYDRATED_RUNNING_RESULT_TOOL_NAMES
