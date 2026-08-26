"""SoAI - Context window standardization helpers [backend/core/models/context_window.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.integers import coerce_positive_exact_int_or_none

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "MODEL_PARAM_STANDARDIZED_NAME",
    "PARAMETER_SEMANTIC_ROLE_CONTEXT_WINDOW",
    "build_standardized_context_display_name",
    "coerce_positive_context_tokens",
    "definition_has_default",
    "extract_context_window_tokens_from_metadata",
    "resolve_semantic_parameter_name",
)

MODEL_PARAM_STANDARDIZED_NAME = "context_window_tokens"
PARAMETER_SEMANTIC_ROLE_CONTEXT_WINDOW = "context_window_tokens"

_CONTEXT_METADATA_KEY_TOKENS: frozenset[str] = frozenset(
    {
        "contextwindowtokens",
        "contextwindow",
        "contextlength",
        "maxcontextlength",
        "maxinputtokens",
        "inputtokenlimit",
        "maxsequencelength",
        "maxmodelcontextlength",
    },
)


def coerce_positive_context_tokens(value: JSONValue) -> int | None:
    return coerce_positive_exact_int_or_none(value, allow_signed_text=False)


def definition_has_default(definition: Mapping[str, JSONValue]) -> bool:
    has_default_field = definition.get("has_default")
    if isinstance(has_default_field, bool):
        return has_default_field
    return "default" in definition


def resolve_semantic_parameter_name(
    schema: Mapping[str, JSONValue],
    semantic_role: str,
) -> str | None:
    normalized_role = semantic_role.strip().lower()
    if not normalized_role:
        return None
    matched_name: str | None = None
    for parameter_name, definition in schema.items():
        if not isinstance(parameter_name, str) or not isinstance(definition, Mapping):
            continue
        semantic_value = definition.get("semantic_role")
        semantic_text = semantic_value.strip().lower() if isinstance(semantic_value, str) else ""
        if semantic_text != normalized_role:
            continue
        if matched_name is not None and matched_name != parameter_name:
            raise ValidationError(
                f"Parameter schema defines duplicate semantic role '{semantic_role}' for '{matched_name}' and '{parameter_name}'.",
            )
        matched_name = parameter_name
    return matched_name


def build_standardized_context_display_name(parameter_name: str) -> str:
    return f"{parameter_name} ({MODEL_PARAM_STANDARDIZED_NAME})"


def extract_context_window_tokens_from_metadata(
    payload: Mapping[str, JSONValue],
) -> int | None:
    return _extract_context_window_tokens(payload, depth=0)


def _extract_context_window_tokens(
    payload: Mapping[str, JSONValue],
    depth: int,
) -> int | None:
    if depth > 7:
        return None
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        normalized_key = _normalize_token_key(key)
        if _is_context_metadata_key(normalized_key):
            if resolved := coerce_positive_context_tokens(value):
                return resolved
        if isinstance(value, Mapping):
            if resolved_nested := _extract_context_window_tokens(value, depth + 1):
                return resolved_nested
            continue
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, Mapping):
                    continue
                if resolved_list_item := _extract_context_window_tokens(item, depth + 1):
                    return resolved_list_item
    return None


def _normalize_token_key(key: str) -> str:
    return "".join(character for character in key.strip().lower() if character.isalnum())


def _is_context_metadata_key(normalized_key: str) -> bool:
    if normalized_key in _CONTEXT_METADATA_KEY_TOKENS:
        return True
    return any(normalized_key.endswith(token) for token in _CONTEXT_METADATA_KEY_TOKENS)
