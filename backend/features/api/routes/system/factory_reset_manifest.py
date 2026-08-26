"""SoAI - Factory reset manifest path collection [backend/features/api/routes/system/factory_reset_manifest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from fastapi import Request

from core.files.path_policy import (
    is_path_within_any_base,
    is_path_within_base,
    is_same_path,
)
from core.logging.trace import get_logger
from core.meta.paths import join_data_abs
from core.plugins.builtin_names import BUILTIN_PLUGIN_NAMES
from core.plugins.file_suffixes import PLUGIN_FILE_SUFFIX
from features.api.runtime.context import ApiContext

__all__ = ("collect_factory_reset_data_root_paths", "collect_factory_reset_manifest")

LOGGER_NAME = "SoAI.features.api.factory_reset_manifest"
STATIC_DEFAULT_DATA_RELATIVE_PATH_PARTS: tuple[tuple[str, ...], ...] = (
    ("vendor", "tika"),
    ("config", "config.default.yaml"),
)


async def collect_factory_reset_manifest(
    *,
    request: Request,
    api_context: ApiContext,
    base_dir: str,
) -> tuple[str, ...]:
    config = api_context.dependencies.config
    paths_to_resolve = _collect_configured_paths(api_context, base_dir)
    system_data_path = api_context.dependencies.files.resolve_path(
        config.require_str_value("SYSTEM.PATHS.SYSTEM_DATA"),
    )
    paths_to_resolve.update(
        collect_factory_reset_data_root_paths(
            base_dir=base_dir,
            system_data_dir=system_data_path,
        ),
    )
    plugins_dir_path = api_context.dependencies.files.resolve_path(
        config.require_str_value("PLUGINS.PATHS.PLUGINS"),
    )
    paths_to_resolve.update(await _collect_plugin_paths(plugins_dir_path))
    return tuple(sorted(_select_safe_existing_paths(request, base_dir, paths_to_resolve)))


def _collect_configured_paths(api_context: ApiContext, base_dir: str) -> set[str]:
    config = api_context.dependencies.config
    configured_keys = (
        "CONFIG_PATH",
        "DATA.DATABASE.PATHS.SYSTEM_DB",
        "PLUGINS.PATHS.BACKENDS",
        "DATA.BACKUP.BACKUPS_PATH",
        "MODELS.MANAGER.PATHS.MODELS",
        "DATA.FILES.PATHS.FILES_STORAGE",
        "SYSTEM.PATHS.TEMP",
        "SYSTEM.PATHS.SYSTEM_ENCRYPTION_KEY",
        "SERVER.WEBUI.WALLPAPER_STORAGE_PATH",
        "OBSERVABILITY.LOGGING.LOGS_PATH",
    )
    paths = {
        join_data_abs(base_dir, "plugins", "venvs"),
        os.path.join(base_dir, "restart_purge.log"),
        os.path.join(base_dir, "__pycache__"),
        join_data_abs(base_dir, "config", "config.yaml"),
        join_data_abs(base_dir, "config", "config.yaml.backup"),
    }
    for config_key in configured_keys:
        configured_path = config.get_str(config_key)
        if configured_path:
            paths.add(api_context.dependencies.files.resolve_path(configured_path))
    return paths


def collect_factory_reset_data_root_paths(
    *,
    base_dir: str,
    system_data_dir: str,
) -> set[str]:
    data_root = os.path.realpath(os.path.abspath(system_data_dir))
    application_root = os.path.realpath(os.path.abspath(base_dir))
    if not is_path_within_base(application_root, data_root):
        return set()
    if not os.path.isdir(data_root):
        return set()
    preserved_paths = _resolve_preserved_relative_paths(base_dir=base_dir, data_root=data_root)
    targets: set[str] = set()
    for entry_name in os.listdir(data_root):
        entry_path = os.path.join(data_root, entry_name)
        relative_path = os.path.normpath(entry_name)
        if relative_path in preserved_paths:
            continue
        if (
            os.path.isdir(entry_path)
            and not os.path.islink(entry_path)
            and _contains_preserved_descendant(relative_path, preserved_paths)
        ):
            targets.update(
                _collect_directory_runtime_paths(
                    directory_path=entry_path,
                    relative_prefix=relative_path,
                    preserved_paths=preserved_paths,
                )
            )
            continue
        targets.add(entry_path)
    return targets


def _resolve_preserved_relative_paths(*, base_dir: str, data_root: str) -> frozenset[str]:
    default_data_root = os.path.realpath(os.path.abspath(join_data_abs(base_dir)))
    if not is_same_path(default_data_root, data_root):
        return frozenset()
    return frozenset(
        os.path.normpath(os.path.join(*parts)) for parts in STATIC_DEFAULT_DATA_RELATIVE_PATH_PARTS
    )


def _contains_preserved_descendant(
    relative_path: str,
    preserved_paths: frozenset[str],
) -> bool:
    descendant_prefix = f"{relative_path}{os.sep}"
    return any(path.startswith(descendant_prefix) for path in preserved_paths)


def _collect_directory_runtime_paths(
    *,
    directory_path: str,
    relative_prefix: str,
    preserved_paths: frozenset[str],
) -> set[str]:
    targets: set[str] = set()
    child_names = os.listdir(directory_path)
    if not child_names:
        return {directory_path}
    for child_name in child_names:
        child_path = os.path.join(directory_path, child_name)
        relative_path = os.path.normpath(os.path.join(relative_prefix, child_name))
        if relative_path in preserved_paths:
            continue
        if (
            os.path.isdir(child_path)
            and not os.path.islink(child_path)
            and _contains_preserved_descendant(relative_path, preserved_paths)
        ):
            targets.update(
                _collect_directory_runtime_paths(
                    directory_path=child_path,
                    relative_prefix=relative_path,
                    preserved_paths=preserved_paths,
                )
            )
            continue
        targets.add(child_path)
    return targets


async def _collect_plugin_paths(plugins_dir_path: str) -> set[str]:
    if not await asyncio.to_thread(os.path.isdir, plugins_dir_path):
        return set()
    builtin_plugins = {f"{name}{PLUGIN_FILE_SUFFIX}" for name in BUILTIN_PLUGIN_NAMES}
    targets: set[str] = set()
    for name in await asyncio.to_thread(os.listdir, plugins_dir_path):
        full_path = os.path.join(plugins_dir_path, name)
        if os.path.isfile(full_path) and (
            name in builtin_plugins or _is_builtin_plugin_support_file(name)
        ):
            continue
        targets.add(full_path)
    return targets


def _select_safe_existing_paths(
    request: Request,
    base_dir: str,
    paths_to_resolve: set[str],
) -> set[str]:
    logger = get_logger(LOGGER_NAME)
    protected_roots = [
        os.path.realpath(os.path.join(base_dir, name))
        for name in (
            "backend",
            "frontend",
            "backend_check",
            "frontend_check",
            "docs",
            "scripts",
            "release_tools",
            "releases",
        )
    ]
    manifest_paths: set[str] = set()
    for path in paths_to_resolve:
        resolved_path = os.path.realpath(path)
        if os.path.basename(resolved_path) in {".git", ".gitignore"}:
            logger.critical(
                "[%s] Refusing protected factory reset target '%s'.",
                request.state.context.trace_id,
                resolved_path,
            )
            continue
        if is_path_within_any_base(protected_roots, resolved_path):
            logger.critical(
                "[%s] Refusing application source target '%s' during factory reset.",
                request.state.context.trace_id,
                resolved_path,
            )
            continue
        if not is_path_within_base(base_dir, resolved_path):
            logger.critical(
                "[%s] Refusing external factory reset target '%s'.",
                request.state.context.trace_id,
                resolved_path,
            )
            continue
        if os.path.exists(resolved_path):
            manifest_paths.add(resolved_path)
    return manifest_paths


def _is_builtin_plugin_support_file(filename: str) -> bool:
    if not filename.endswith(".py"):
        return False
    stem = filename[:-3]
    for plugin_name in BUILTIN_PLUGIN_NAMES:
        if stem == plugin_name or stem.startswith(f"{plugin_name}_"):
            return True
    return False
