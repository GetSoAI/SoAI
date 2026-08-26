"""SoAI - Config schema reconciliation and strict validation [backend/core/config/schema_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

    type ConfigDict = dict[str, ConfigValue]

__all__ = (
    "ConfigReconcileOutcome",
    "reconcile_config_schema",
)


@dataclass(frozen=True, slots=True)
class ConfigReconcileOutcome:
    merged: ConfigDict
    changed: bool
    changed_paths: tuple[str, ...]


def reconcile_config_schema(*, schema: ConfigDict, user: ConfigDict) -> ConfigReconcileOutcome:
    merged: ConfigDict = {}
    changed_paths: list[str] = []
    changed = False
    for key, schema_value in schema.items():
        if key not in user:
            merged[key] = _deep_copy_config_value(schema_value)
            changed = True
            changed_paths.append(key)
            continue
        user_value = user[key]
        merged_value, nested_changed, nested_paths = _merge_value(
            schema_value=schema_value,
            user_value=user_value,
            prefix=key,
        )
        merged[key] = merged_value
        if nested_changed:
            changed = True
            changed_paths.extend(nested_paths)

    for key in user:
        if key not in schema:
            changed = True
            changed_paths.append(key)

    _validate_value_types(schema_value=schema, user_value=merged, prefix="")

    return ConfigReconcileOutcome(
        merged=merged,
        changed=bool(changed),
        changed_paths=tuple(sorted(set(changed_paths))),
    )


def _merge_value(
    *,
    schema_value: ConfigValue,
    user_value: ConfigValue,
    prefix: str,
) -> tuple[ConfigValue, bool, list[str]]:
    if isinstance(schema_value, dict):
        if not isinstance(user_value, dict):
            raise ValidationError(
                f"Config key '{prefix}' must be a mapping.",
                details={"key": prefix, "expected": "mapping", "actual": type(user_value).__name__},
            )
        merged: ConfigDict = {}
        changed = False
        paths: list[str] = []
        for key, nested_schema in schema_value.items():
            if not isinstance(key, str) or not key:
                continue
            nested_prefix = f"{prefix}.{key}"
            if key not in user_value:
                merged[key] = _deep_copy_config_value(nested_schema)
                changed = True
                paths.append(nested_prefix)
                continue
            merged_value, nested_changed, nested_paths = _merge_value(
                schema_value=nested_schema,
                user_value=user_value[key],
                prefix=nested_prefix,
            )
            merged[key] = merged_value
            if nested_changed:
                changed = True
                paths.extend(nested_paths)
        for key in user_value:
            if key not in schema_value:
                changed = True
                paths.append(f"{prefix}.{key}")
        return merged, changed, paths

    return user_value, False, []


def _validate_value_types(
    *,
    schema_value: ConfigValue,
    user_value: ConfigValue,
    prefix: str,
) -> None:
    if isinstance(schema_value, dict):
        if not isinstance(user_value, dict):
            raise ValidationError(
                _format_type_error(prefix=prefix, expected="mapping", actual=user_value),
                details={"key": prefix, "expected": "mapping", "actual": type(user_value).__name__},
            )
        for key, nested_schema in schema_value.items():
            if not isinstance(key, str) or not key:
                continue
            if key not in user_value:
                raise ValidationError(
                    f"Missing required config key: {f'{prefix}.' if prefix else ''}{key}",
                )
            nested_prefix = f"{prefix}.{key}" if prefix else key
            _validate_value_types(
                schema_value=nested_schema,
                user_value=user_value[key],
                prefix=nested_prefix,
            )
        return

    expected = _value_type_name(schema_value)
    actual = _value_type_name(user_value)
    if expected == actual:
        return
    if _numeric_type(expected) and _numeric_type(actual):
        return
    raise ValidationError(
        _format_type_error(prefix=prefix, expected=expected, actual=user_value),
        details={
            "key": prefix,
            "expected": expected,
            "actual": actual,
        },
    )


def _format_type_error(*, prefix: str, expected: str, actual: ConfigValue) -> str:
    key_label = prefix or "<root>"
    return f"Config key '{key_label}' has invalid type; expected {expected}, got {type(actual).__name__}."


def _numeric_type(value_type: str) -> bool:
    return value_type in {"int", "float"}


def _value_type_name(value: ConfigValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, dict):
        return "mapping"
    if isinstance(value, list):
        return "sequence"
    if isinstance(value, tuple):
        return "sequence"
    return type(value).__name__


def _deep_copy_config_value(value: ConfigValue) -> ConfigValue:
    if isinstance(value, dict):
        copied: ConfigDict = {}
        for key, nested in value.items():
            if isinstance(key, str):
                copied[key] = _deep_copy_config_value(nested)
        return copied
    if isinstance(value, list):
        return [_deep_copy_config_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_deep_copy_config_value(item) for item in value)
    return value
