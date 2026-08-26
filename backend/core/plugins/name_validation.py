"""SoAI - Plugin name validation helpers [backend/core/plugins/name_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.validation.strings import coerce_optional_trimmed_str

__all__ = ("require_plugin_name",)


def require_plugin_name(plugin_name: str, *, field_name: str = "plugin_name") -> str:
    normalized = coerce_optional_trimmed_str(plugin_name)
    if normalized is None:
        raise ValidationError(f"{field_name} is required.")
    return normalized
