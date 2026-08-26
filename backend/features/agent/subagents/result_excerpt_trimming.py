"""SoAI - Subagent result excerpt trimming helpers [backend/features/agent/subagents/result_excerpt_trimming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "trim_prompt_summary_result_excerpt",
    "trim_running_preview_result_excerpt",
)

_ELLIPSIS = "..."

_RUNNING_PREVIEW_MAX_CHARS = 1200
_SUMMARY_PROMPT_MAX_CHARS = 1400


def trim_running_preview_result_excerpt(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) <= _RUNNING_PREVIEW_MAX_CHARS:
        return normalized
    tail_len = max(0, _RUNNING_PREVIEW_MAX_CHARS - len(_ELLIPSIS))
    if tail_len <= 0:
        return _ELLIPSIS
    tail = normalized[-tail_len:].lstrip()
    return f"{_ELLIPSIS}{tail}"


def trim_prompt_summary_result_excerpt(value: str) -> str:
    normalized = value.strip()
    if len(normalized) <= _SUMMARY_PROMPT_MAX_CHARS:
        return normalized
    head_len = max(0, _SUMMARY_PROMPT_MAX_CHARS - len(_ELLIPSIS))
    if head_len <= 0:
        return _ELLIPSIS
    head = normalized[:head_len].rstrip()
    return f"{head}{_ELLIPSIS}"
