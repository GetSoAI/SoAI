"""SoAI - Ordered uniqueness helpers [backend/core/collections/ordered_uniqueness.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable

__all__ = ("unique_sequence",)


def unique_sequence(values: Iterable[str] | None, *, omit_falsy: bool = False) -> tuple[str, ...]:
    if values is None:
        return ()
    filtered: Iterable[str]
    if omit_falsy:
        filtered = (value for value in values if value)
    else:
        filtered = values
    return tuple(dict.fromkeys(filtered))
