"""SoAI - Files root path value coercion helpers [backend/core/files/workspace_path_value.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue

__all__ = (
    "coerce_workspace_path_value",
    "require_workspace_path_value",
)


def coerce_workspace_path_value(value: JSONValue) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if "\x00" in stripped:
        return None
    return stripped


def require_workspace_path_value(value: JSONValue, *, error_message: str) -> str:
    resolved = coerce_workspace_path_value(value)
    if resolved is None:
        raise ValidationError(error_message)
    return resolved
