"""SoAI - Portable plugin identifiers [backend/core/plugins/portable_identifiers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.errors.exceptions import ValidationError

__all__ = ("is_portable_plugin_identifier", "require_portable_plugin_identifier")

_PORTABLE_PLUGIN_IDENTIFIER_PATTERN = r"[a-z0-9](?:[a-z0-9_-]{0,99})\Z"


def _is_windows_reserved_identifier(value: str) -> bool:
    if value in frozenset(("aux", "clock$", "con", "nul", "prn")):
        return True
    return len(value) == 4 and value[:3] in frozenset(("com", "lpt")) and value[3] in "123456789"


def is_portable_plugin_identifier(value: str) -> bool:
    if not isinstance(value, str):
        return False
    return bool(
        re.fullmatch(_PORTABLE_PLUGIN_IDENTIFIER_PATTERN, value)
    ) and not _is_windows_reserved_identifier(value)


def require_portable_plugin_identifier(value: str, *, field_name: str) -> str:
    if is_portable_plugin_identifier(value):
        return value
    raise ValidationError(
        f"{field_name} must be a lowercase portable plugin identifier between 1 and 100 characters."
    )
