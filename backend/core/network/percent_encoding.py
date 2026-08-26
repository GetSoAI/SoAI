"""SoAI - Percent-encoding validation [backend/core/network/percent_encoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from string import hexdigits

__all__ = ("is_valid_percent_encoding",)


def is_valid_percent_encoding(value: str) -> bool:
    index = 0
    while index < len(value):
        if value[index] != "%":
            index += 1
            continue
        if index + 2 >= len(value):
            return False
        if value[index + 1] not in hexdigits or value[index + 2] not in hexdigits:
            return False
        index += 3
    return True
