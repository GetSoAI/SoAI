"""SoAI - Config summary field coercion primitives [backend/core/config/summary_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.value_types import ConfigValue
from core.serialization.json import normalize_for_json
from core.validation.coercion import coerce_json_dict_stringify_non_json_values
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "coerce_summary_bool",
    "coerce_summary_int",
    "coerce_summary_mapping",
)


def coerce_summary_bool(value: ConfigValue | JSONValue) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def coerce_summary_int(value: ConfigValue | JSONValue) -> int | None:
    if is_strict_int(value):
        return value
    return None


def coerce_summary_mapping(value: ConfigValue | JSONValue) -> JSONDict | None:
    if not isinstance(value, dict):
        return None
    return coerce_json_dict_stringify_non_json_values(normalize_for_json(value))
