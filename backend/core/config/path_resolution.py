"""SoAI - Config path resolution primitives [backend/core/config/path_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.meta.paths import get_config_yaml_path

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

__all__ = (
    "ConfigPathResolutionError",
    "ConfigPathSetting",
    "iter_config_path_settings",
    "resolve_all_paths_in_config_with_layout",
    "resolve_config_file_path",
    "resolve_default_config_schema_path",
    "resolve_path",
)

_UNRESOLVED_POSIX_ENV_PATTERN = r"\$(\{[A-Za-z_][A-Za-z0-9_]*\}|[A-Za-z_][A-Za-z0-9_]*)"
_UNRESOLVED_WINDOWS_ENV_PATTERN = r"%(?P<name>[A-Za-z_][A-Za-z0-9_]*)%"


class ConfigPathResolutionError(Exception): ...


@dataclass(frozen=True, slots=True)
class ConfigPathSetting:
    dotted_key: str
    parent: MutableMapping[str, ConfigValue]
    key: str
    value: str
    relative_to_system_data: bool


def resolve_default_config_schema_path(config_path: str) -> str:
    return os.path.join(os.path.dirname(config_path), "config.default.yaml")


def resolve_path(path: str | os.PathLike[str] | None, base_path: str) -> str | None:
    if path is None:
        return None
    if isinstance(path, os.PathLike):
        path = os.fspath(path)
    if not isinstance(path, str):
        raise ConfigPathResolutionError("Configured path must be a string or os.PathLike.")
    candidate = path.strip()
    if not candidate:
        raise ConfigPathResolutionError("Configured path is empty.")
    expanded = os.path.expandvars(candidate)
    expanded = os.path.expanduser(os.path.expandvars(expanded))
    if not expanded.strip():
        raise ConfigPathResolutionError("Configured path resolved to empty.")
    if expanded.startswith("~"):
        raise ConfigPathResolutionError(f"Configured path references unknown home '{path}'.")
    if re.search(_UNRESOLVED_POSIX_ENV_PATTERN, expanded) or re.search(
        _UNRESOLVED_WINDOWS_ENV_PATTERN,
        expanded,
    ):
        raise ConfigPathResolutionError(
            f"Configured path contains unresolved environment variable '{path}'.",
        )
    resolved = expanded if os.path.isabs(expanded) else os.path.join(base_path, expanded)
    return os.path.normpath(resolved)


def resolve_config_file_path(
    base_dir: str | os.PathLike[str],
    *,
    configured_path: str | os.PathLike[str] | None,
) -> str:
    if not isinstance(base_dir, str | os.PathLike):
        raise ConfigPathResolutionError("base_dir must be a string or os.PathLike.")
    if not str(base_dir).strip():
        raise ConfigPathResolutionError("base_dir is required.")
    base_dir_text: str = os.fspath(base_dir)
    base_path = os.path.abspath(base_dir_text)
    if configured_path is not None and str(configured_path).strip():
        resolved = resolve_path(configured_path, base_path)
        if resolved is None:
            raise ConfigPathResolutionError("SOAI_CONFIG_PATH did not resolve to a value.")
        return os.path.abspath(resolved)
    return get_config_yaml_path(base_path)


def iter_config_path_settings(
    current_dict: MutableMapping[str, ConfigValue],
    *,
    state_dotted_keys: frozenset[str],
    base_dotted_keys: frozenset[str],
) -> Iterator[ConfigPathSetting]:
    def _iterate_mapping(
        mapping: MutableMapping[str, ConfigValue], prefix: list[str]
    ) -> Iterator[ConfigPathSetting]:
        for key, value in mapping.items():
            if isinstance(value, MutableMapping):
                nested_mapping: MutableMapping[str, ConfigValue] = value
                yield from _iterate_mapping(nested_mapping, prefix + [key])
                continue
            if not isinstance(value, str) or not value.strip():
                continue
            dotted = ".".join(prefix + [key])
            if dotted in base_dotted_keys:
                relative_to_system_data = False
            elif dotted in state_dotted_keys or "PATHS" in prefix:
                relative_to_system_data = True
            elif key.endswith(("_PATH", "_DIR", "_FILE")):
                relative_to_system_data = False
            else:
                continue
            yield ConfigPathSetting(dotted, mapping, key, value, relative_to_system_data)

    yield from _iterate_mapping(current_dict, [])


def resolve_all_paths_in_config_with_layout(
    current_dict: MutableMapping[str, ConfigValue],
    *,
    base_path: str,
    system_data_path: str,
    state_dotted_keys: frozenset[str],
    base_dotted_keys: frozenset[str],
) -> None:
    for setting in iter_config_path_settings(
        current_dict,
        state_dotted_keys=state_dotted_keys,
        base_dotted_keys=base_dotted_keys,
    ):
        resolved = resolve_path(
            setting.value,
            system_data_path if setting.relative_to_system_data else base_path,
        )
        if resolved is not None:
            setting.parent[setting.key] = resolved
