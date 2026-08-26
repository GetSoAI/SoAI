"""SoAI - WebUI preview contract retry prompts [backend/features/api/runtime/preview_contract_retry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.internal_retry_prompt import (
    build_internal_retry_instruction_text,
    build_internal_retry_user_message,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_preview_contract_retry_message",
    "build_preview_contract_retry_system_message",
)

_PREVIEW_RETRY_PREFIX = "<soai_preview_contract_retry>"


def _build_preview_contract_retry_body(failure_detail: str | None = None) -> str:
    lines = [
        "Repair the output now so it follows the SoAI WebUI preview contract.",
        "Use canonical preview references with [[preview:<type>:<target>]] syntax in the visible assistant response body.",
        "Never use a plain URL for links, images, video, or other content supported by the SoAI WebUI preview system.",
        "URLs are allowed only inside fenced code blocks when you are writing code examples. Do not put plain URLs in prose or inside backticks.",
        "Do not rely on plain URLs, Markdown images, or HTML image tags.",
        "Do not use tool calls, tool arguments, tool results, notifications, or any other side channel to deliver preview references or the main gallery content.",
        "Return only the corrected assistant response.",
    ]
    normalized_failure_detail = str(failure_detail or "").strip()
    if normalized_failure_detail:
        lines.append(f"Correct this specific problem: {normalized_failure_detail}")
    return "\n".join(lines)


def build_preview_contract_retry_system_message(
    failure_detail: str | None = None,
) -> str:
    lines = [
        _PREVIEW_RETRY_PREFIX,
        build_internal_retry_instruction_text(_build_preview_contract_retry_body(failure_detail)),
        "</soai_preview_contract_retry>",
    ]
    return "\n".join(lines)


def build_preview_contract_retry_message(
    failure_detail: str | None = None,
) -> JSONDict:
    return build_internal_retry_user_message(_build_preview_contract_retry_body(failure_detail))
