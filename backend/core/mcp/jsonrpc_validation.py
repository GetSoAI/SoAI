"""SoAI - MCP JSON-RPC shape validation primitives [backend/core/mcp/jsonrpc_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int

__all__ = (
    "read_optional_jsonrpc_nonempty_str",
    "read_optional_jsonrpc_nonempty_str_list",
    "require_jsonrpc_dict",
    "require_jsonrpc_dict_list",
    "require_jsonrpc_int",
    "require_jsonrpc_nonempty_str",
    "require_jsonrpc_nonempty_str_list",
)


def require_jsonrpc_int(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    message: str,
    minimum: int | None = None,
) -> int:
    if not is_strict_int(value):
        raise build_error(message)
    if minimum is not None and value < minimum:
        raise build_error(message)
    return value


def require_jsonrpc_dict(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    message: str,
    allow_empty: bool = False,
) -> JSONDict:
    normalized = coerce_json_dict(value)
    if normalized is None or (not allow_empty and not normalized):
        raise build_error(message)
    return normalized


def require_jsonrpc_nonempty_str(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    message: str,
) -> str:
    if not isinstance(value, str):
        raise build_error(message)
    normalized = value.strip()
    if not normalized:
        raise build_error(message)
    return normalized


def require_jsonrpc_nonempty_str_list(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    message: str,
) -> list[str]:
    if not isinstance(value, list):
        raise build_error(message)
    normalized_items: list[str] = []
    for entry in value:
        normalized_items.append(
            require_jsonrpc_nonempty_str(entry, build_error=build_error, message=message),
        )
    return normalized_items


def read_optional_jsonrpc_nonempty_str(value: JSONValue) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def read_optional_jsonrpc_nonempty_str_list(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    message: str,
) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise build_error(message)
    normalized_items: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise build_error(message)
        normalized = entry.strip()
        if normalized:
            normalized_items.append(normalized)
    return normalized_items or None


def require_jsonrpc_dict_list(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    message: str,
) -> list[JSONDict]:
    if not isinstance(value, list):
        raise build_error(message)
    normalized_items: list[JSONDict] = []
    for entry in value:
        normalized_items.append(
            require_jsonrpc_dict(entry, build_error=build_error, message=message),
        )
    return normalized_items
