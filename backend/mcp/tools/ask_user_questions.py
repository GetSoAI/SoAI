"""SoAI - MCP ask_user questions normalization [backend/mcp/tools/ask_user_questions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.argument_fields import (
    optional_bounded_string,
    require_bounded_string,
)
from mcp.tools.argument_scalars import parse_bool_strict_default
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("normalize_questions",)

_MAX_QUESTION_COUNT = 6
_MAX_QUESTION_ID_LENGTH = 64
_MAX_QUESTION_TEXT_LENGTH = 4096
_MAX_HEADER_LENGTH = 256
_MAX_OPTION_COUNT = 6
_MIN_OPTION_COUNT = 2
_MAX_OPTION_LABEL_LENGTH = 256
_MAX_OPTION_DESCRIPTION_LENGTH = 1024
_SHAPE_EXAMPLE = (
    '{"question":"Which environment?","header":"Deploy","options":['
    '{"label":"Staging","description":"Recommended for testing"},'
    '{"label":"Production","description":"Live traffic"}]}'
)


def _normalize_option(value: JSONValue, *, question_index: int, option_index: int) -> JSONDict:
    if not isinstance(value, dict):
        raise MCPToolError(
            -32602,
            f"questions[{question_index}].options[{option_index}] must be an object with label and description",
        )
    label = require_bounded_string(
        value.get("label"),
        field=f"questions[{question_index}].options[{option_index}].label",
        max_length=_MAX_OPTION_LABEL_LENGTH,
    )
    description = require_bounded_string(
        value.get("description"),
        field=f"questions[{question_index}].options[{option_index}].description",
        max_length=_MAX_OPTION_DESCRIPTION_LENGTH,
    )
    return {"label": label, "description": description}


def _normalize_question_id(value: JSONValue, *, question_index: int) -> str | None:
    if value is None:
        return None
    return require_bounded_string(
        value,
        field=f"questions[{question_index}].id",
        max_length=_MAX_QUESTION_ID_LENGTH,
    )


def _normalize_options(value: JSONValue, *, question_index: int) -> list[JSONDict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise MCPToolError(-32602, f"questions[{question_index}].options must be an array")
    if len(value) < _MIN_OPTION_COUNT or len(value) > _MAX_OPTION_COUNT:
        raise MCPToolError(
            -32602,
            f"questions[{question_index}].options must contain {_MIN_OPTION_COUNT}-{_MAX_OPTION_COUNT} entries when provided",
        )
    options: list[JSONDict] = []
    labels: set[str] = set()
    for option_index, option_value in enumerate(value):
        option = _normalize_option(
            option_value,
            question_index=question_index,
            option_index=option_index,
        )
        label_value = option.get("label")
        if not isinstance(label_value, str):
            raise MCPToolError(
                -32602,
                f"questions[{question_index}].options[{option_index}].label must be a string",
            )
        label = label_value
        if label in labels:
            raise MCPToolError(
                -32602,
                f"questions[{question_index}].options has duplicate label: {label}",
            )
        labels.add(label)
        options.append(option)
    return options


def _next_generated_question_id(existing_ids: set[str], next_auto_id: int) -> tuple[str, int]:
    candidate = next_auto_id
    while str(candidate) in existing_ids:
        candidate += 1
    return (str(candidate), candidate + 1)


def _normalize_question(
    value: JSONValue,
    *,
    question_index: int,
    existing_ids: set[str],
    next_auto_id: int,
) -> tuple[JSONDict, int]:
    if not isinstance(value, dict):
        raise MCPToolError(
            -32602,
            f"questions[{question_index}] must match this shape: {_SHAPE_EXAMPLE}",
        )
    question_id = _normalize_question_id(value.get("id"), question_index=question_index)
    if question_id is None:
        question_id, next_auto_id = _next_generated_question_id(existing_ids, next_auto_id)
    if question_id in existing_ids:
        raise MCPToolError(-32602, f"questions has duplicate id: {question_id}")
    question = require_bounded_string(
        value.get("question"),
        field=f"questions[{question_index}].question",
        max_length=_MAX_QUESTION_TEXT_LENGTH,
    )
    header = optional_bounded_string(
        value.get("header"),
        field=f"questions[{question_index}].header",
        max_length=_MAX_HEADER_LENGTH,
    )
    multi_select = parse_bool_strict_default(
        value.get("multi_select"),
        field_name=f"questions[{question_index}].multi_select",
        default=False,
    )
    is_secret = parse_bool_strict_default(
        value.get("is_secret"),
        field_name=f"questions[{question_index}].is_secret",
        default=False,
    )
    options = _normalize_options(value.get("options"), question_index=question_index)
    normalized: JSONDict = {
        "id": question_id,
        "question": question,
        "multiSelect": multi_select,
        "isSecret": is_secret,
        "options": options,
    }
    if header is not None:
        normalized["header"] = header
    return (normalized, next_auto_id)


def normalize_questions(value: JSONValue) -> list[JSONDict]:
    if not isinstance(value, list):
        raise MCPToolError(-32602, "questions must be an array")
    if not value:
        raise MCPToolError(-32602, "questions must contain at least one item")
    if len(value) > _MAX_QUESTION_COUNT:
        raise MCPToolError(-32602, f"questions must have <= {_MAX_QUESTION_COUNT} entries")
    questions: list[JSONDict] = []
    question_ids: set[str] = set()
    next_auto_id = 0
    for question_index, question_value in enumerate(value):
        question, next_auto_id = _normalize_question(
            question_value,
            question_index=question_index,
            existing_ids=question_ids,
            next_auto_id=next_auto_id,
        )
        question_id = require_bounded_string(
            question.get("id"),
            field=f"questions[{question_index}].id",
            max_length=_MAX_QUESTION_ID_LENGTH,
        )
        question_ids.add(question_id)
        questions.append(question)
    return questions
