"""SoAI - Configuration change detection helpers [backend/core/config/changes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("compute_core_changed_config_areas", "compute_top_level_changed_keys")


def _get_core_change_area_depths() -> dict[str, int]:
    return {
        "SYSTEM": 2,
        "SERVER": 2,
        "API": 3,
        "MODELS": 2,
        "PLUGINS": 1,
        "TOOLS": 2,
        "DATA": 2,
        "INTEGRATIONS": 2,
        "AUTOMATION": 1,
        "OBSERVABILITY": 2,
    }


def compute_top_level_changed_keys(
    *,
    previous: Mapping[str, JSONValue] | None,
    current: Mapping[str, JSONValue],
) -> frozenset[str]:
    if previous is None:
        return frozenset(current.keys())
    changed: set[str] = set()
    all_keys = set(previous.keys()) | set(current.keys())
    for key in all_keys:
        if previous.get(key) != current.get(key):
            changed.add(key)
    return frozenset(changed)


def compute_core_changed_config_areas(
    *,
    previous: Mapping[str, JSONValue] | None,
    current: Mapping[str, JSONValue],
) -> frozenset[str]:
    if previous is None:
        return frozenset(_iter_current_core_areas(current))
    changed: set[str] = set()
    root_keys = set(previous.keys()) | set(current.keys())
    for root_key in root_keys:
        if not isinstance(root_key, str):
            continue
        depth = _get_core_change_area_depths().get(root_key, 1)
        previous_value = previous.get(root_key)
        current_value = current.get(root_key)
        changed.update(
            _collect_changed_areas(
                previous_value=previous_value,
                current_value=current_value,
                prefix=root_key,
                remaining_depth=depth - 1,
            ),
        )
    return frozenset(changed)


def _iter_current_core_areas(current: Mapping[str, JSONValue]) -> set[str]:
    areas: set[str] = set()
    for root_key, value in current.items():
        if not isinstance(root_key, str):
            continue
        depth = _get_core_change_area_depths().get(root_key, 1)
        areas.update(
            _collect_present_areas(
                value=value,
                prefix=root_key,
                remaining_depth=depth - 1,
            ),
        )
    return areas


def _collect_present_areas(
    *,
    value: JSONValue,
    prefix: str,
    remaining_depth: int,
) -> set[str]:
    if remaining_depth <= 0 or not isinstance(value, Mapping):
        return {prefix}
    areas: set[str] = set()
    for key, child_value in value.items():
        if isinstance(key, str):
            areas.update(
                _collect_present_areas(
                    value=child_value,
                    prefix=f"{prefix}.{key}",
                    remaining_depth=remaining_depth - 1,
                ),
            )
    if not areas:
        areas.add(prefix)
    return areas


def _collect_changed_areas(
    *,
    previous_value: JSONValue | None,
    current_value: JSONValue | None,
    prefix: str,
    remaining_depth: int,
) -> set[str]:
    if previous_value == current_value:
        return set()
    if remaining_depth <= 0:
        return {prefix}
    if not isinstance(previous_value, Mapping) or not isinstance(current_value, Mapping):
        return {prefix}
    areas: set[str] = set()
    keys = set(previous_value.keys()) | set(current_value.keys())
    for key in keys:
        if not isinstance(key, str):
            continue
        areas.update(
            _collect_changed_areas(
                previous_value=previous_value.get(key),
                current_value=current_value.get(key),
                prefix=f"{prefix}.{key}",
                remaining_depth=remaining_depth - 1,
            ),
        )
    if not areas:
        areas.add(prefix)
    return areas
