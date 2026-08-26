"""SoAI - Plugin model variant naming helpers [backend/core/plugins/model_variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("normalize_variant_name",)


def normalize_variant_name(value: str) -> str:
    lowered_value = value.lower()
    normalized_chars: list[str] = []
    previous_was_separator = True
    for char in lowered_value:
        if char.isascii() and char.isalnum():
            normalized_chars.append(char)
            previous_was_separator = False
        elif not previous_was_separator:
            normalized_chars.append("-")
            previous_was_separator = True
    normalized = "".join(normalized_chars).strip("-")
    return normalized or lowered_value
