"""SoAI - Plugin clone path retargeting helpers [backend/plugins/clone_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json_value import copy_json_dict
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ()


def resolve_default_models_dir(manager: PluginManagerRuntimeProtocol, plugin_name: str) -> str:
    models_root = manager.dependencies.core.config.require_str("MODELS.MANAGER.PATHS.MODELS")
    return os.path.abspath(
        manager.dependencies.core.files.resolve_path(os.path.join(models_root, plugin_name)),
    )


def retarget_cloned_model_paths(
    manager: PluginManagerRuntimeProtocol,
    config_data: JSONDict,
    source_plugin_name: str,
    target_plugin_name: str,
    source_models_path: str | None,
    target_models_path: str | None,
) -> tuple[JSONDict, bool]:
    if not isinstance(config_data, dict):
        raise ValidationError("Cloned configuration must be a dictionary.")
    source_defaults = {resolve_default_models_dir(manager, source_plugin_name)}
    if source_models_path:
        source_defaults.add(
            os.path.abspath(manager.dependencies.core.files.resolve_path(source_models_path)),
        )
    target_models_dir = (
        os.path.abspath(manager.dependencies.core.files.resolve_path(target_models_path))
        if target_models_path
        else resolve_default_models_dir(manager, target_plugin_name)
    )
    updated_config = copy_json_dict(config_data)
    changed = False
    model_dirs = updated_config.get("MODEL_DIRS")
    if isinstance(model_dirs, list):
        new_dirs: list[JSONValue] = []
        for entry in model_dirs:
            if isinstance(entry, str) and entry.strip():
                normalized = os.path.abspath(manager.dependencies.core.files.resolve_path(entry))
                if normalized in source_defaults:
                    new_dirs.append(target_models_dir)
                    changed = True
                else:
                    new_dirs.append(entry)
            else:
                new_dirs.append(entry)
        if changed:
            updated_config["MODEL_DIRS"] = new_dirs
    models_override = updated_config.get("MODELS_PATH_OVERRIDE")
    if isinstance(models_override, str) and models_override.strip():
        normalized_override = os.path.abspath(
            manager.dependencies.core.files.resolve_path(models_override),
        )
        if normalized_override in source_defaults:
            updated_config["MODELS_PATH_OVERRIDE"] = target_models_dir
            changed = True
    return (updated_config, changed)
