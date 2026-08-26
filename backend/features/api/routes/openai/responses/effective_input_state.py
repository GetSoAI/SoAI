"""SoAI - OpenAI Responses effective input request-state helpers [backend/features/api/routes/openai/responses/effective_input_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.errors.exceptions import StateError
from core.types.json import JSONDict, is_json_dict
from core.types.json_value import copy_json_dict

__all__ = (
    "require_effective_input_items",
    "store_effective_input_items",
)


def store_effective_input_items(request: Request, items: tuple[JSONDict, ...]) -> None:
    request.state.openai_responses_effective_input_items = tuple(
        copy_json_dict(item) for item in items
    )


def require_effective_input_items(request: Request) -> tuple[JSONDict, ...]:
    try:
        value: tuple[JSONDict, ...] = request.state.openai_responses_effective_input_items
    except AttributeError as exception:
        raise StateError(
            "Responses effective input items are missing from request state.",
        ) from exception
    if not isinstance(value, tuple):
        raise StateError("Responses effective input items are invalid.")
    items: list[JSONDict] = []
    for item in value:
        if not is_json_dict(item):
            raise StateError("Responses effective input items are invalid.")
        items.append(copy_json_dict(item))
    return tuple(items)
