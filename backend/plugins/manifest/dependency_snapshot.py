"""SoAI - Shared plugin dependency snapshot parsing [backend/plugins/manifest/dependency_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_value
from core.validation.string_sequences import normalize_strict_string_sequence

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.types.json import JSONValue

__all__ = (
    "PluginDependencySnapshot",
    "dependency_snapshot_from_manifest",
    "dependency_snapshot_from_record",
    "missing_plugin_dependencies",
)


@dataclass(frozen=True, slots=True)
class PluginDependencySnapshot:
    plugin_names: tuple[str, ...]
    package_names: tuple[str, ...]


def _dependency_snapshot_from_json_value(value: JSONValue) -> PluginDependencySnapshot:
    if not isinstance(value, dict):
        raise ValidationError("Expected dependencies JSON object.")
    plugin_names = normalize_strict_string_sequence(
        value.get("plugins"),
        field_name="dependencies.plugins",
    )
    package_names = normalize_strict_string_sequence(
        value.get("packages"),
        field_name="dependencies.packages",
    )
    return PluginDependencySnapshot(
        plugin_names=tuple(plugin_names),
        package_names=tuple(package_names),
    )


def dependency_snapshot_from_manifest(
    manifest: Mapping[str, JSONValue],
) -> PluginDependencySnapshot:
    return _dependency_snapshot_from_json_value(manifest.get("dependencies"))


def dependency_snapshot_from_record(record: Mapping[str, JSONValue]) -> PluginDependencySnapshot:
    raw_dependencies = record.get("dependencies")
    if isinstance(raw_dependencies, str):
        parsed = parse_json_value(raw_dependencies)
    else:
        parsed = raw_dependencies
    return _dependency_snapshot_from_json_value(parsed)


def missing_plugin_dependencies(
    snapshot: PluginDependencySnapshot,
    *,
    available_plugin_names: set[str],
    plugin_name: str,
) -> list[str]:
    return sorted(
        dependency_name
        for dependency_name in snapshot.plugin_names
        if dependency_name != plugin_name and dependency_name not in available_plugin_names
    )
