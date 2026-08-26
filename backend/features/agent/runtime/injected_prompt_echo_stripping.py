"""SoAI - Agent injected prompt echo stripping [backend/features/agent/runtime/injected_prompt_echo_stripping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.agent.prompt_injection_slots import (
    AGENT_INSTRUCTIONS_PREFIXES,
    INJECTED_PROMPT_XML_TAGS,
)

__all__ = (
    "InjectedPromptEchoStrippingResult",
    "strip_echoed_injected_prompt_blocks",
)

_ECHO_XML_TAGS: tuple[str, ...] = (
    *INJECTED_PROMPT_XML_TAGS,
    "soai_internal_retry_instruction",
    "soai_preview_contract",
    "soai_preview_contract_retry",
    "soai_content_preview_feedback",
)


@dataclass(frozen=True, slots=True)
class InjectedPromptEchoStrippingResult:
    sanitized_text: str
    stripped: bool
    stripped_tags: tuple[str, ...]


def strip_echoed_injected_prompt_blocks(text: str) -> InjectedPromptEchoStrippingResult:
    remainder = text.lstrip()
    if not remainder:
        return InjectedPromptEchoStrippingResult(
            sanitized_text=text,
            stripped=False,
            stripped_tags=(),
        )
    stripped_tags: list[str] = []
    while remainder:
        consumed = _consume_one_injected_block(remainder)
        if consumed is None:
            if stripped_tags:
                return InjectedPromptEchoStrippingResult(
                    sanitized_text=remainder,
                    stripped=True,
                    stripped_tags=tuple(stripped_tags),
                )
            return InjectedPromptEchoStrippingResult(
                sanitized_text=text,
                stripped=False,
                stripped_tags=(),
            )
        remainder, tag = consumed
        stripped_tags.append(tag)
        remainder = remainder.lstrip()
    return InjectedPromptEchoStrippingResult(
        sanitized_text="",
        stripped=True,
        stripped_tags=tuple(stripped_tags),
    )


def _consume_one_injected_block(text: str) -> tuple[str, str] | None:
    if text.startswith("<"):
        for tag in _ECHO_XML_TAGS:
            open_marker = f"<{tag}>"
            if not text.startswith(open_marker):
                continue
            close_marker = f"</{tag}>"
            close_index = text.find(close_marker, len(open_marker))
            if close_index < 0:
                return None
            after_close = text[close_index + len(close_marker) :]
            return (after_close, tag)
        return None
    for prefix in AGENT_INSTRUCTIONS_PREFIXES:
        if not text.startswith(prefix):
            continue
        close_marker = "</INSTRUCTIONS>"
        close_index = text.find(close_marker)
        if close_index < 0:
            return None
        after_close = text[close_index + len(close_marker) :]
        return (after_close, "agents_instructions")
    return None
