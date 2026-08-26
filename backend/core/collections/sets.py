"""SoAI - Set diff primitives for change detection [backend/core/collections/sets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable

__all__ = ("compute_set_deltas",)


def compute_set_deltas[Item](
    previous: Iterable[Item],
    current: Iterable[Item],
) -> tuple[set[Item], set[Item]]:
    previous_set = set(previous)
    current_set = set(current)
    removed = previous_set - current_set
    added = current_set - previous_set
    return (removed, added)
