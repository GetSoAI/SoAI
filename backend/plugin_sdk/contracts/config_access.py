"""SoAI - Plugin SDK configuration access helpers [backend/plugin_sdk/contracts/config_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue

__all__ = (
    "get_config_bool",
    "get_config_float",
    "get_config_int",
    "get_config_str",
)


def get_config_str(
    config: Mapping[str, JSONValue],
    key: str,
    *,
    default: str | None = None,
    allow_empty: bool = False,
) -> str | None:
    raw = config.get(key)
    if raw is None:
        return default
    if not isinstance(raw, str):
        raise ValidationError(f"Config key '{key}' must be a string.")
    value = raw.strip()
    if value:
        return value
    return "" if allow_empty else default


def get_config_bool(
    config: Mapping[str, JSONValue],
    key: str,
    *,
    default: bool | None = None,
) -> bool | None:
    raw = config.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int | float) and raw in (0, 1):
        return bool(raw)
    if isinstance(raw, str):
        lowered = raw.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    raise ValidationError(f"Config key '{key}' must be a boolean.")


def get_config_int(
    config: Mapping[str, JSONValue],
    key: str,
    *,
    default: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    raw = config.get(key)
    if raw is None:
        return default
    value: int
    if isinstance(raw, bool):
        raise ValidationError(f"Config key '{key}' must be an integer.")
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, float):
        if not raw.is_integer():
            raise ValidationError(f"Config key '{key}' must be an integer.")
        value = int(raw)
    elif isinstance(raw, str):
        text = raw.strip()
        if not text:
            return default
        try:
            value = int(text, 10)
        except ValueError as exception:
            raise ValidationError(f"Config key '{key}' must be an integer.") from exception
    else:
        raise ValidationError(f"Config key '{key}' must be an integer.")
    if minimum is not None and value < minimum:
        raise ValidationError(f"Config key '{key}' must be >= {minimum}.")
    if maximum is not None and value > maximum:
        raise ValidationError(f"Config key '{key}' must be <= {maximum}.")
    return value


def get_config_float(
    config: Mapping[str, JSONValue],
    key: str,
    *,
    default: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    raw = config.get(key)
    if raw is None:
        return default
    value: float
    if isinstance(raw, bool):
        raise ValidationError(f"Config key '{key}' must be a number.")
    if isinstance(raw, int | float):
        value = float(raw)
    elif isinstance(raw, str):
        text = raw.strip()
        if not text:
            return default
        try:
            value = float(text)
        except ValueError as exception:
            raise ValidationError(f"Config key '{key}' must be a number.") from exception
    else:
        raise ValidationError(f"Config key '{key}' must be a number.")
    if minimum is not None and value < minimum:
        raise ValidationError(f"Config key '{key}' must be >= {minimum}.")
    if maximum is not None and value > maximum:
        raise ValidationError(f"Config key '{key}' must be <= {maximum}.")
    return value
