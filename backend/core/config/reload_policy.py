"""SoAI - Configuration reload-sensitive key and parameter policy [backend/core/config/reload_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "filter_reload_parameters",
    "reload_sensitive_keys",
)


def reload_sensitive_keys(
    schema: Mapping[str, JSONValue] | None,
    keys: Iterable[str],
) -> set[str]:
    if not schema:
        return set[str]()
    sensitive = set[str]()
    for key in keys:
        definition = schema.get(key)
        if isinstance(definition, Mapping) and definition.get("requires_reload"):
            sensitive.add(key)
    return sensitive


def filter_reload_parameters(
    schema: Mapping[str, JSONValue] | None,
    parameters: Mapping[str, JSONValue] | None,
) -> dict[str, JSONValue]:
    if not schema or not parameters:
        return {}
    reload_keys = reload_sensitive_keys(schema, parameters.keys())
    return {key: parameters[key] for key in reload_keys if key in parameters}
