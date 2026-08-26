"""SoAI - Plugin identity normalization [backend/plugins/identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exceptions import ValidationError
from core.plugins.file_suffixes import PLUGIN_FILE_SUFFIX
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.types.json import JSONValue
from core.validation.identifiers import is_identifier_strictly_alnum

__all__ = (
    "normalize_plugin_display_name",
    "normalize_plugin_lookup_key",
    "normalize_plugin_target_name",
    "require_plugin_file_stem",
    "require_plugin_identifier",
)


def normalize_plugin_lookup_key(value: JSONValue) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def normalize_plugin_target_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return require_portable_plugin_identifier(normalized, field_name="target_name")


def require_plugin_identifier(value: str, *, invalid_message: str) -> str:
    if not is_identifier_strictly_alnum(value):
        raise ValidationError(invalid_message)
    return value


def require_plugin_file_stem(filename: str, *, invalid_message: str) -> str:
    if not filename or not filename.endswith(PLUGIN_FILE_SUFFIX):
        raise ValidationError(f"Invalid plugin filename. Expected a {PLUGIN_FILE_SUFFIX} file.")
    raw_name = filename[: -len(PLUGIN_FILE_SUFFIX)]
    normalized_name = raw_name.strip()
    if not normalized_name:
        raise ValidationError("Invalid plugin filename. Name cannot be empty.")
    if normalized_name != raw_name:
        raise ValidationError(invalid_message)
    require_plugin_identifier(normalized_name, invalid_message=invalid_message)
    if normalized_name.startswith("_"):
        raise ValidationError(
            "Invalid plugin filename. Plugin names cannot start with an underscore.",
        )
    return normalized_name


def normalize_plugin_display_name(
    plugin_name: str,
    plugin_data: Mapping[str, JSONValue],
) -> str:
    display_name_value = plugin_data.get("name")
    if isinstance(display_name_value, str) and display_name_value.strip():
        return display_name_value.strip()
    return plugin_name
