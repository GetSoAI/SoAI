"""SoAI - MCP text statistics tool implementation [backend/mcp/tools/text_stats.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.types.json import JSONDict

__all__ = ("tool_text_stats",)

_ALLOWED_KEYS: frozenset[str] = frozenset({"text"})


def _build_text_statistics(prompt_token_counter: PromptTokenCounter, text: str) -> JSONDict:
    characters = len(text)
    characters_no_spaces = len(
        text.replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", ""),
    )
    words = len(text.split()) if text.strip() else 0
    sentences = len(re.findall("[.!?]+(?:\\s|$)", text)) if text.strip() else 0
    paragraphs = (
        len([paragraph for paragraph in re.split("\\n\\s*\\n", text) if paragraph.strip()])
        if text.strip()
        else 0
    )
    lines = len(text.splitlines()) if text else 0
    reading_time = round(words / 200, 2) if words > 0 else 0
    speaking_time = round(words / 150, 2) if words > 0 else 0
    token_count = prompt_token_counter.count_text_tokens(text)
    return {
        "characters": characters,
        "characters_no_spaces": characters_no_spaces,
        "words": words,
        "sentences": sentences,
        "paragraphs": paragraphs,
        "lines": lines,
        "tokens": token_count,
        "reading_time_minutes": reading_time,
        "speaking_time_minutes": speaking_time,
    }


async def tool_text_stats(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    text = get_arg(arguments, "text")
    if not isinstance(text, str):
        raise MCPToolError(
            -32602,
            f"Parameter 'text' must be a string, got {type(text).__name__}",
        )
    prompt_token_counter = utility_tools.prompt_token_counter
    return await prompt_token_counter.run_blocking(
        _build_text_statistics,
        prompt_token_counter,
        text,
    )
