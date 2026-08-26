"""SoAI - Plugin package cache and lease paths [backend/plugins/package_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import StateError, ValidationError
from core.files.path_policy import ensure_path_within_base_lexical
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from plugins.identity import require_plugin_identifier

__all__ = (
    "COMPLETION_RECORD_NAME",
    "get_plugin_package_cache_directory",
    "get_plugin_package_cache_lock_target",
    "get_plugin_package_hash_directory",
    "get_plugin_package_hash_lock_target",
    "get_plugin_package_lease_directory",
)

COMPLETION_RECORD_NAME = ".soai-package.json"


def _require_temp_directory(temp_directory: str) -> str:
    resolved = str(temp_directory or "").strip()
    if not resolved:
        raise ValidationError("Plugin package temp directory is not configured.")
    return os.path.realpath(resolved)


def get_plugin_package_cache_directory(temp_directory: str, plugin_name: str) -> str:
    require_plugin_identifier(plugin_name, invalid_message=f"Invalid plugin name '{plugin_name}'.")
    base_path = _require_temp_directory(temp_directory)
    return ensure_path_within_base_lexical(
        base_path,
        os.path.join(base_path, "plugin_packages", plugin_name),
        description="Plugin package cache path",
        error_cls=ValidationError,
    )


def get_plugin_package_hash_directory(
    temp_directory: str,
    plugin_name: str,
    archive_hash: str,
) -> str:
    try:
        require_canonical_sha256_hexdigest(
            archive_hash,
            label="Plugin package archive hash",
        )
    except StateError as exception:
        raise ValidationError(
            "Plugin package archive hash must be lowercase SHA-256."
        ) from exception
    cache_directory = get_plugin_package_cache_directory(temp_directory, plugin_name)
    return ensure_path_within_base_lexical(
        cache_directory,
        os.path.join(cache_directory, archive_hash),
        description="Plugin package hash path",
        error_cls=ValidationError,
    )


def get_plugin_package_cache_lock_target(temp_directory: str, plugin_name: str) -> str:
    require_plugin_identifier(plugin_name, invalid_message=f"Invalid plugin name '{plugin_name}'.")
    base_path = _require_temp_directory(temp_directory)
    return ensure_path_within_base_lexical(
        base_path,
        os.path.join(base_path, f".plugin-package-cache-{plugin_name}"),
        description="Plugin package cache lock target",
        error_cls=ValidationError,
    )


def get_plugin_package_hash_lock_target(
    temp_directory: str,
    plugin_name: str,
    archive_hash: str,
) -> str:
    get_plugin_package_hash_directory(temp_directory, plugin_name, archive_hash)
    base_path = _require_temp_directory(temp_directory)
    return ensure_path_within_base_lexical(
        base_path,
        os.path.join(base_path, f".plugin-package-hash-{plugin_name}-{archive_hash}"),
        description="Plugin package hash lock target",
        error_cls=ValidationError,
    )


def get_plugin_package_lease_directory(temp_directory: str, plugin_name: str) -> str:
    require_plugin_identifier(plugin_name, invalid_message=f"Invalid plugin name '{plugin_name}'.")
    base_path = _require_temp_directory(temp_directory)
    return ensure_path_within_base_lexical(
        base_path,
        os.path.join(base_path, "plugin_package_leases", plugin_name),
        description="Plugin package lease path",
        error_cls=ValidationError,
    )
