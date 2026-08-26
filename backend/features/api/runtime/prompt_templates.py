"""SoAI - Prompt template runtime helpers [backend/features/api/runtime/prompt_templates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.prompts.colors import validate_prompt_color
from core.prompts.protocols_database import DatabasePromptsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "create_prompt",
    "list_prompts",
    "normalize_prompt_fields",
    "update_prompt",
)


def normalize_prompt_fields(name: str, content: str) -> tuple[str, str]:
    normalized_name = str(name or "").strip() or "Untitled Prompt"
    normalized_content = str(content or "")
    return (normalized_name, normalized_content)


async def create_prompt(
    database_prompts: DatabasePromptsProtocol,
    user_id: int,
    name: str,
    content: str,
    color: str | None = None,
) -> JSONDict:
    normalized_name, normalized_content = normalize_prompt_fields(name, content)
    normalized_color = validate_prompt_color(color)
    return await database_prompts.create_prompt(
        user_id,
        normalized_name,
        normalized_content,
        normalized_color,
    )


async def list_prompts(
    database_prompts: DatabasePromptsProtocol,
    user_id: int,
    color: str | None = None,
) -> list[JSONDict]:
    normalized_color = validate_prompt_color(color)
    return await database_prompts.list_prompts(user_id, normalized_color)


async def update_prompt(
    database_prompts: DatabasePromptsProtocol,
    prompt_id: str,
    user_id: int,
    name: str,
    content: str,
    color: str | None = None,
) -> JSONDict | None:
    normalized_name, normalized_content = normalize_prompt_fields(name, content)
    normalized_color = validate_prompt_color(color)
    return await database_prompts.update_prompt(
        prompt_id,
        user_id,
        normalized_name,
        normalized_content,
        normalized_color,
    )
