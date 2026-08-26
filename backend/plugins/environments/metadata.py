"""SoAI - Plugin environment metadata validation [backend/plugins/environments/metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import platform
import sys
import sysconfig
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import open_text
from core.hardware.reservation_claims import claim_reserved_write
from core.serialization.json import serialize_json_pretty_sorted
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONDict, JSONValue, is_str_list

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = (
    "PLUGIN_ENV_METADATA_FILENAME",
    "PluginEnvironmentIdentity",
    "build_plugin_environment_metadata",
    "environment_freeze_matches",
    "environment_metadata_matches",
    "read_plugin_environment_metadata",
    "write_plugin_environment_metadata",
)

PLUGIN_ENV_METADATA_FILENAME = "soai_plugin_env.json"


@dataclass(frozen=True, slots=True)
class PluginEnvironmentIdentity:
    plugin_name: str
    worker_baseline_requirements: tuple[str, ...]
    package_dependencies: tuple[str, ...]


def _python_version() -> str:
    return ".".join(str(part) for part in sys.version_info[:3])


def _implementation_cache_tag() -> str:
    cache_tag = sys.implementation.cache_tag
    return cache_tag if isinstance(cache_tag, str) and cache_tag else ""


def _platform_tag() -> str:
    configured = sysconfig.get_platform()
    return configured if isinstance(configured, str) and configured else platform.system()


def build_plugin_environment_metadata(
    identity: PluginEnvironmentIdentity,
    *,
    pip_freeze_all: list[str],
) -> JSONDict:
    return {
        "plugin_name": identity.plugin_name,
        "python_version": _python_version(),
        "implementation_cache_tag": _implementation_cache_tag(),
        "platform_tag": _platform_tag(),
        "worker_baseline_requirements": list(identity.worker_baseline_requirements),
        "package_dependencies": list(identity.package_dependencies),
        "pip_freeze_all": list(pip_freeze_all),
    }


def _read_str(payload: JSONDict, key: str) -> str:
    value: JSONValue | None = payload.get(key)
    return value if isinstance(value, str) else ""


def _read_str_list(payload: JSONDict, key: str) -> list[str]:
    value: JSONValue | None = payload.get(key)
    return list(value) if is_str_list(value) else []


def read_plugin_environment_metadata(env_path: str) -> JSONDict | None:
    metadata_path = os.path.join(env_path, PLUGIN_ENV_METADATA_FILENAME)
    if not os.path.isfile(metadata_path):
        return None
    with open_text(metadata_path, encoding="utf-8") as handle:
        parsed = parse_json_value(handle.read())
    if not isinstance(parsed, dict):
        raise ValidationError("Plugin environment metadata must be a JSON object.")
    return dict(parsed)


def environment_metadata_matches(
    metadata: JSONDict | None,
    identity: PluginEnvironmentIdentity,
) -> bool:
    if metadata is None:
        return False
    if _read_str(metadata, "plugin_name") != identity.plugin_name:
        return False
    if _read_str(metadata, "python_version") != _python_version():
        return False
    if _read_str(metadata, "implementation_cache_tag") != _implementation_cache_tag():
        return False
    if _read_str(metadata, "platform_tag") != _platform_tag():
        return False
    if _read_str_list(metadata, "worker_baseline_requirements") != list(
        identity.worker_baseline_requirements,
    ):
        return False
    return _read_str_list(metadata, "package_dependencies") == list(identity.package_dependencies)


def environment_freeze_matches(metadata: JSONDict | None, pip_freeze_all: list[str]) -> bool:
    if metadata is None:
        return False
    return _read_str_list(metadata, "pip_freeze_all") == sorted(pip_freeze_all)


def write_plugin_environment_metadata(
    env_path: str,
    metadata: JSONDict,
    storage_manager: StorageManagerProtocol,
) -> None:
    metadata_path = os.path.join(env_path, PLUGIN_ENV_METADATA_FILENAME)
    content = serialize_json_pretty_sorted(metadata)
    required_bytes = len(content.encode("utf-8"))
    with (
        storage_manager.reserve_disk_space(
            path=metadata_path,
            required_bytes=required_bytes,
            operation="plugins.environments.write_metadata",
            details={"path": metadata_path, "required_bytes": required_bytes},
        ) as reservation,
        claim_reserved_write(reservation, size_bytes=required_bytes),
    ):
        atomic_write_text_content(
            metadata_path,
            content,
            encoding="utf-8",
            errors="strict",
            ensure_parent=False,
            fsync=True,
        )
