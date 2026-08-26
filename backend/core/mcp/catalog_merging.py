"""SoAI - Collision-safe catalog merging helpers [backend/core/mcp/catalog_merging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exceptions import StateError

__all__ = ("merge_named_catalog_items",)


def merge_named_catalog_items[ItemT](
    existing: Mapping[str, ItemT],
    incoming: Mapping[str, ItemT],
    *,
    existing_label: str,
    incoming_label: str,
) -> dict[str, ItemT]:
    collisions = set(existing.keys()) & set(incoming.keys())
    if collisions:
        collisions_text = ", ".join(sorted(collisions))
        raise StateError(
            f"Catalog item name collision while merging {incoming_label} into {existing_label}: {collisions_text}",
        )
    merged = dict(existing)
    merged.update(incoming)
    return merged
