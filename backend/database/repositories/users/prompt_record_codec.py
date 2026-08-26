"""SoAI - Prompt repository row normalization [backend/database/repositories/users/prompt_record_codec.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.prompts.colors import validate_prompt_color
from core.timing.epoch import epoch_ms
from database.core.sqlite_numbers import coerce_int_from_sqlite
from database.repositories.row_formatting import format_row

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("format_prompt_row", "normalize_prompt_content", "prepare_prompt_record")

LOGGER_NAME = "SoAI.database.repositories.prompt_record_codec"


def normalize_prompt_content(content: JSONValue | None) -> str:
    text = "" if content is None else str(content)
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def prepare_prompt_record(
    name: str,
    content: str,
    color: str | None,
) -> tuple[str, str, str | None]:
    sanitized_name = ("" if name is None else str(name)).strip() or "Untitled Prompt"
    sanitized_content = normalize_prompt_content(content)
    sanitized_color = validate_prompt_color(color)
    return sanitized_name, sanitized_content, sanitized_color


def format_prompt_row(row: SQLiteRowDict | None) -> JSONDict | None:
    logger = get_logger(LOGGER_NAME)
    if row is None:
        return None
    formatted = format_row(row)
    if formatted is None:
        return None
    formatted["id"] = str(formatted.get("id", ""))
    user_id = coerce_int_from_sqlite(row.get("user_id"), default=0)
    formatted["user_id"] = 0 if user_id is None else user_id
    now_ms = epoch_ms()
    created_at_ms = coerce_int_from_sqlite(
        row.get("created_at_ms"),
        default=now_ms,
    )
    if created_at_ms is None:
        created_at_ms = now_ms
    formatted["created_at_ms"] = created_at_ms
    modified_at_ms = coerce_int_from_sqlite(
        row.get("modified_at_ms"),
        default=created_at_ms,
    )
    formatted["modified_at_ms"] = created_at_ms if modified_at_ms is None else modified_at_ms
    name_value = formatted.get("name")
    formatted["name"] = "" if name_value is None else str(name_value)
    formatted["content"] = normalize_prompt_content(formatted.get("content"))
    color_value = formatted.get("color")
    color_text = color_value if isinstance(color_value, str) else None
    try:
        formatted["color"] = validate_prompt_color(color_text)
    except ValueError as error:
        logger.warning(
            "Ignoring unsupported prompt color for prompt %s: %s",
            formatted.get("id"),
            str(error),
        )
        formatted["color"] = None
    return formatted
