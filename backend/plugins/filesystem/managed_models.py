"""SoAI - Managed plugin model tree cleanup [backend/plugins/filesystem/managed_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.config.layout import BASE_DOTTED_KEYS, STATE_DOTTED_KEYS
from core.errors.exceptions import SecurityError, StateError, ValidationError
from core.files.managed_file_deletion import delete_managed_path
from core.files.managed_storage_errors import FileDeletionSecurityError
from core.files.path_policy import (
    is_path_overlap_with_base,
    is_path_within_base,
    is_same_path,
)
from core.files.protected_sqlite_runtime_paths import (
    ensure_directory_excludes_protected_sqlite_runtime_files,
)
from core.plugins.runtime_services import PluginPathResolver
from core.serialization.json import normalize_for_json
from core.types.json_value import coerce_json_dict
from plugins.clone.clone_committed_cleanup import (
    COMMITTED_CLONE_MODEL_ARTIFACT_TYPES,
    release_committed_clone_markers,
)
from plugins.identity import require_plugin_identifier

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("remove_plugin_managed_models",)

OPERATION_REMOVE_MANAGED_MODELS = "plugins.registry.delete.remove_plugin_managed_models"


def _normalized_model_path(path: str) -> str:
    resolved = os.path.abspath(path)
    if not resolved or os.path.dirname(resolved) == resolved:
        raise StateError(
            "Refusing to remove a filesystem root as a managed model path.",
            operation=OPERATION_REMOVE_MANAGED_MODELS,
        )
    return resolved


def _resolved_parent_path(path: str) -> str:
    return os.path.join(os.path.realpath(os.path.dirname(path)), os.path.basename(path))


def _require_safe_managed_path(
    manager: PluginManagerRuntimeProtocol,
    models_path: str,
) -> str:
    config = manager.dependencies.core.config
    files = manager.dependencies.core.files
    configured_models_root = files.resolve_path(config.require_str("MODELS.MANAGER.PATHS.MODELS"))
    resolved_models_path = _resolved_parent_path(models_path)
    if is_path_within_base(models_path, configured_models_root):
        raise StateError(
            "Refusing to remove a protected shared root as managed plugin models.",
            operation=OPERATION_REMOVE_MANAGED_MODELS,
        )
    database_path = config.get_str("DATA.DATABASE.PATHS.SYSTEM_DB")
    ensure_directory_excludes_protected_sqlite_runtime_files(
        resolved_models_path,
        files.resolve_path(database_path) if database_path else None,
        operation=OPERATION_REMOVE_MANAGED_MODELS,
    )
    protected_paths = [
        manager.dependencies.infrastructure.config_manager.get_config_path_sync("core")
    ]
    excluded_config_keys = {
        "DATA.DATABASE.PATHS.SYSTEM_DB",
        "MODELS.MANAGER.PATHS.MODELS",
        "SYSTEM.PATHS.SYSTEM_DATA",
    }
    for config_key in (STATE_DOTTED_KEYS | BASE_DOTTED_KEYS) - excluded_config_keys:
        configured_path = config.get_str(config_key)
        if configured_path:
            protected_paths.append(files.resolve_path(configured_path))
    for protected_path in protected_paths:
        if is_path_overlap_with_base(protected_path, models_path):
            raise StateError(
                "Refusing to remove a protected shared root as managed plugin models.",
                operation=OPERATION_REMOVE_MANAGED_MODELS,
            )
    return resolved_models_path


async def _journaled_model_path(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> str | None:
    repository = manager.dependencies.databases.plugins.clone_transactions
    transaction = await repository.get_committed_for_target(plugin_name)
    if transaction is None:
        return None
    model_artifacts = [
        artifact
        for artifact in await repository.list_artifacts(transaction.task_id)
        if artifact.artifact_type == "models" and artifact.state == "published"
    ]
    if len(model_artifacts) > 1:
        raise StateError(
            "Committed clone has multiple published managed model paths.",
            operation=OPERATION_REMOVE_MANAGED_MODELS,
            details={"plugin_name": plugin_name},
        )
    if not model_artifacts:
        return None
    return _normalized_model_path(model_artifacts[0].final_path)


async def _configured_model_path(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> tuple[str, bool]:
    loaded_config = await manager.dependencies.infrastructure.config_manager.load_config(
        plugin_name,
        force_reload=True,
    )
    plugin_config: JSONDict
    if loaded_config is None:
        plugin_config = {}
    else:
        normalized_plugin_config = coerce_json_dict(normalize_for_json(loaded_config))
        if normalized_plugin_config is None:
            raise StateError(
                "Plugin configuration is invalid for managed model cleanup.",
                operation=OPERATION_REMOVE_MANAGED_MODELS,
                details={"plugin_name": plugin_name},
            )
        plugin_config = normalized_plugin_config
    override_value = plugin_config.get("MODELS_PATH_OVERRIDE")
    has_override = "MODELS_PATH_OVERRIDE" in plugin_config
    if has_override and not isinstance(override_value, str):
        raise StateError(
            "Plugin configuration is invalid for managed model cleanup.",
            operation=OPERATION_REMOVE_MANAGED_MODELS,
            details={"plugin_name": plugin_name},
        )
    resolver = PluginPathResolver(
        plugin_name,
        manager.dependencies.core.config,
        manager.dependencies.core.files,
        plugin_config,
    )
    return (_normalized_model_path(resolver.models_directory()), loaded_config is not None)


def _same_model_path(left_path: str, right_path: str) -> bool:
    return (
        is_same_path(left_path, right_path)
        or is_same_path(os.path.realpath(left_path), os.path.realpath(right_path))
        or is_same_path(_resolved_parent_path(left_path), _resolved_parent_path(right_path))
    )


async def _resolve_model_paths(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> tuple[str, ...]:
    journaled_path = await _journaled_model_path(manager, plugin_name)
    configured_path, config_available = await _configured_model_path(manager, plugin_name)
    if journaled_path is not None and not config_available:
        return (journaled_path,)
    if journaled_path is None or _same_model_path(configured_path, journaled_path):
        return (configured_path,)
    return (configured_path, journaled_path)


async def _require_unshared_model_paths(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    model_paths: tuple[str, ...],
) -> None:
    records = await manager.dependencies.databases.plugins.get_all_plugins()
    for record in records:
        other_name = record.get("plugin_name") if isinstance(record, dict) else None
        if not isinstance(other_name, str) or not other_name.strip():
            raise StateError(
                "Plugin catalog contains an invalid managed model owner.",
                operation=OPERATION_REMOVE_MANAGED_MODELS,
            )
        normalized_other_name = other_name.strip()
        if normalized_other_name == plugin_name:
            continue
        other_model_paths = await _resolve_model_paths(manager, normalized_other_name)
        for models_path in model_paths:
            if any(
                is_path_overlap_with_base(models_path, other_path)
                for other_path in other_model_paths
            ):
                raise StateError(
                    "Managed model path is shared with another plugin.",
                    operation=OPERATION_REMOVE_MANAGED_MODELS,
                    details={
                        "plugin_name": plugin_name,
                        "conflicting_plugin_name": normalized_other_name,
                    },
                )


async def remove_plugin_managed_models(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> None:
    try:
        async with manager.dependencies.infrastructure.config_manager.plugin_config_mutation_scope(
            plugin_name
        ):
            require_plugin_identifier(
                plugin_name,
                invalid_message="Invalid plugin name for managed model removal.",
            )
            model_paths = await _resolve_model_paths(manager, plugin_name)
            deletion_paths = tuple(
                _require_safe_managed_path(manager, models_path) for models_path in model_paths
            )
            await _require_unshared_model_paths(manager, plugin_name, model_paths)
            await release_committed_clone_markers(
                manager,
                plugin_name,
                artifact_types=COMMITTED_CLONE_MODEL_ARTIFACT_TYPES,
                allow_missing_models=True,
            )
            for deletion_path in deletion_paths:
                await delete_managed_path(os.path.dirname(deletion_path), deletion_path)
                if os.path.lexists(deletion_path):
                    raise StateError(
                        "Managed model removal did not remove the target path.",
                        operation=OPERATION_REMOVE_MANAGED_MODELS,
                        details={"plugin_name": plugin_name},
                    )
    except (FileDeletionSecurityError, OSError, SecurityError, ValidationError) as exception:
        raise StateError(
            "Failed to remove managed plugin models.",
            operation=OPERATION_REMOVE_MANAGED_MODELS,
            details={"plugin_name": plugin_name},
            cause=exception,
        ) from exception
