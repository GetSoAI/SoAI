"""SoAI - Internal retry prompt markers and leak detection [backend/core/openai/internal_retry_prompt.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.content_text_coercion import coerce_openai_content_text

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "INTERNAL_RETRY_CLOSE_TAG",
    "INTERNAL_RETRY_OPEN_TAG",
    "build_internal_retry_instruction_text",
    "build_internal_retry_user_message",
    "is_internal_retry_message",
    "is_internal_retry_output_leak",
)

INTERNAL_RETRY_OPEN_TAG = "<soai_internal_retry_instruction>"
INTERNAL_RETRY_CLOSE_TAG = "</soai_internal_retry_instruction>"
_LEAK_PREFIXES: tuple[str, ...] = (
    "the user is asking",
    "the user asked",
    "the user said",
    "the user wants",
    "the previous assistant",
    "previous assistant",
    "the assistant response",
    "the assistant output",
    "repair the output now",
    "this turn requires the soai webui preview contract",
    "retry with canonical preview references",
    "repair the previous output",
    "internal retry instruction",
)
_LEAK_MARKERS: tuple[str, ...] = (
    "visible assistant response body",
    "soai webui preview contract",
    "canonical preview references",
    "do not mention this repair instruction",
    "do not mention this retry instruction",
    "output attempted a tool call",
    "repair the output now",
    "soai_content_preview_feedback",
    "soai_preview_contract",
    "soai_preview_contract_retry",
    "tool-call protocol",
    "tool-call json",
)


def build_internal_retry_instruction_text(content: str) -> str:
    normalized = str(content or "").strip()
    if not normalized:
        raise ValidationError("Internal retry instruction content must be non-empty.")
    return f"{INTERNAL_RETRY_OPEN_TAG}\n{normalized}\n{INTERNAL_RETRY_CLOSE_TAG}"


def build_internal_retry_user_message(content: str) -> JSONDict:
    return {
        "role": "user",
        "content": build_internal_retry_instruction_text(content),
    }


def _content_has_internal_retry_instruction(content: JSONValue) -> bool:
    text = coerce_openai_content_text(content)
    return INTERNAL_RETRY_OPEN_TAG in text


def is_internal_retry_message(message: JSONDict) -> bool:
    content = message.get("content")
    return _content_has_internal_retry_instruction(content)


def is_internal_retry_output_leak(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    if INTERNAL_RETRY_OPEN_TAG in lowered or INTERNAL_RETRY_CLOSE_TAG in lowered:
        return True
    leading = lowered[:600].lstrip()
    for prefix in _LEAK_PREFIXES:
        if leading.startswith(prefix):
            return True
    if (
        "the user" not in leading
        and "assistant" not in leading
        and "repair" not in leading
        and "retry" not in leading
        and "soai_" not in leading
    ):
        return False
    return any(marker in leading for marker in _LEAK_MARKERS)
