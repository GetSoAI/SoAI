"""SoAI - Redacted config patch value preservation [backend/core/config/redacted_patch_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.security.sensitive_detection import is_sensitive_key_name

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("remove_redacted_sensitive_patch_values",)


def _clean_sequence_value(value: list[JSONValue], *, placeholder: str) -> list[JSONValue]:
    cleaned: list[JSONValue] = []
    for item in value:
        if isinstance(item, Mapping):
            cleaned.append(remove_redacted_sensitive_patch_values(item, placeholder=placeholder))
            continue
        if isinstance(item, list):
            cleaned.append(_clean_sequence_value(item, placeholder=placeholder))
            continue
        cleaned.append(item)
    return cleaned


def _clean_patch_entry(key: str, value: JSONValue, *, placeholder: str) -> tuple[bool, JSONValue]:
    if isinstance(value, Mapping):
        return True, remove_redacted_sensitive_patch_values(value, placeholder=placeholder)
    if isinstance(value, list):
        return True, _clean_sequence_value(value, placeholder=placeholder)
    if (
        isinstance(value, str)
        and value == placeholder
        and is_sensitive_key_name(key, include_credential_containers=True)
    ):
        return False, None
    return True, value


def remove_redacted_sensitive_patch_values(
    changes: Mapping[str, JSONValue],
    *,
    placeholder: str,
) -> JSONDict:
    cleaned: JSONDict = {}
    for raw_key, raw_value in changes.items():
        key = str(raw_key)
        should_keep, cleaned_value = _clean_patch_entry(key, raw_value, placeholder=placeholder)
        if should_keep:
            cleaned[key] = cleaned_value
    return cleaned
