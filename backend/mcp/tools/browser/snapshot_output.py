"""SoAI - Browser snapshot output shaping [backend/mcp/tools/browser/snapshot_output.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from mcp.tools.browser.aria_snapshot_lines import filter_snapshot_text_by_roles

__all__ = ("filter_snapshot_output_text", "merge_snapshot_alias_maps")


def merge_snapshot_alias_maps(
    combined_aliases: dict[str, str],
    combined_conflicts: set[str],
    alias_updates: dict[str, str],
    alias_conflicts: set[str],
) -> None:
    for alias in alias_conflicts:
        combined_aliases.pop(alias, None)
        combined_conflicts.add(alias)
    for alias, ref in alias_updates.items():
        if alias in combined_conflicts:
            continue
        existing = combined_aliases.get(alias)
        if existing is None:
            combined_aliases[alias] = ref
            continue
        if existing != ref:
            combined_aliases.pop(alias, None)
            combined_conflicts.add(alias)


def filter_snapshot_output_text(snapshot_text: str, *, allowed_roles: set[str]) -> str:
    return filter_snapshot_text_by_roles(snapshot_text, allowed_roles=allowed_roles)
