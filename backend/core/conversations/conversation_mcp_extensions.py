"""SoAI - Conversation MCP extension normalization [backend/core/conversations/conversation_mcp_extensions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json_value import coerce_json_dict
from core.validation.strict_numbers import require_int_in_range_strict
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "CONVERSATION_MCP_EXTENSION_FIELDS",
    "CONVERSATION_MCP_WEB_SEARCH_FIELD",
    "WEB_SEARCH_MAX_RESULTS_MAX",
    "WEB_SEARCH_MAX_RESULTS_MIN",
    "normalize_conversation_mcp_extensions",
    "normalize_conversation_web_search_config",
)

CONVERSATION_MCP_WEB_SEARCH_FIELD = "web_search"
CONVERSATION_MCP_EXTENSION_FIELDS: frozenset[str] = frozenset((CONVERSATION_MCP_WEB_SEARCH_FIELD,))
WEB_SEARCH_MAX_RESULTS_MIN = 1
WEB_SEARCH_MAX_RESULTS_MAX = 50

_WEB_SEARCH_CONFIG_FIELDS: frozenset[str] = frozenset(
    (
        "enabled",
        "default_provider",
        "max_results",
    ),
)


def normalize_conversation_mcp_extensions(
    raw: Mapping[str, JSONValue] | None,
) -> JSONDict:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValidationError("Conversation MCP config must be an object.")
    extensions: JSONDict = {}
    if CONVERSATION_MCP_WEB_SEARCH_FIELD in raw:
        web_search_config = normalize_conversation_web_search_config(
            raw.get(CONVERSATION_MCP_WEB_SEARCH_FIELD),
        )
        extensions[CONVERSATION_MCP_WEB_SEARCH_FIELD] = web_search_config
    return extensions


def normalize_conversation_web_search_config(value: JSONValue) -> JSONDict:
    if value is None:
        return {}
    payload = coerce_json_dict(value)
    if payload is None:
        raise ValidationError("Conversation MCP web_search config must be an object.")
    for field_name in payload:
        if field_name not in _WEB_SEARCH_CONFIG_FIELDS:
            raise ValidationError(
                f"Conversation MCP web_search config contains unsupported field '{field_name}'.",
            )
    normalized: JSONDict = {}
    _normalize_enabled(payload, normalized)
    _normalize_default_provider(payload, normalized)
    _normalize_max_results(payload, normalized)
    return normalized


def _normalize_enabled(payload: JSONDict, normalized: JSONDict) -> None:
    if "enabled" not in payload:
        return
    value = payload.get("enabled")
    if value is None:
        return
    if not isinstance(value, bool):
        raise ValidationError("Conversation MCP web_search.enabled must be a boolean.")
    normalized["enabled"] = value


def _normalize_default_provider(payload: JSONDict, normalized: JSONDict) -> None:
    if "default_provider" not in payload:
        return
    value = payload.get("default_provider")
    if value is None:
        return
    provider = coerce_optional_trimmed_str(value)
    if provider is None:
        if isinstance(value, str):
            return
        raise ValidationError("Conversation MCP web_search.default_provider must be a string.")
    normalized["default_provider"] = provider


def _normalize_max_results(payload: JSONDict, normalized: JSONDict) -> None:
    if "max_results" not in payload:
        return
    value = payload.get("max_results")
    if value is None:
        return
    normalized["max_results"] = require_int_in_range_strict(
        value,
        minimum=WEB_SEARCH_MAX_RESULTS_MIN,
        maximum=WEB_SEARCH_MAX_RESULTS_MAX,
        error_message=f"Conversation MCP web_search.max_results must be an integer from {WEB_SEARCH_MAX_RESULTS_MIN} to {WEB_SEARCH_MAX_RESULTS_MAX}.",
    )
