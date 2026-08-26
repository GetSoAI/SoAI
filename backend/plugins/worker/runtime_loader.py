"""SoAI - Plugin worker module loading helpers [backend/plugins/worker/runtime_loader.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import inspect
import os
import sys
from importlib import util

from core.errors.exceptions import ValidationError
from core.plugins.base_plugin import BasePlugin
from core.types.json import JSONDict
from core.validation.record_fields import require_json_object
from plugins.path_safety import build_plugin_module_name
from plugins.worker.class_contract import (
    ensure_declared_openai_capability_flags,
    ensure_declared_plugin_metadata,
)

__all__ = (
    "load_plugin_class",
    "read_model_map",
)


def load_plugin_class(
    plugin_name: str,
    *,
    plugin_package_root: str,
    plugin_entrypoint_path: str,
) -> type[BasePlugin]:
    resolved_root = os.path.realpath(plugin_package_root)
    resolved_entrypoint = os.path.realpath(plugin_entrypoint_path)
    expected_entrypoint = os.path.join(resolved_root, "__init__.py")
    if resolved_entrypoint != expected_entrypoint:
        raise ValidationError("Plugin package entrypoint must be the root __init__.py.")
    if os.path.islink(plugin_entrypoint_path) or not os.path.isfile(plugin_entrypoint_path):
        raise ValidationError("Plugin package entrypoint must be a regular file.")
    module_name = build_plugin_module_name(
        plugin_name=plugin_name,
        module_name_override=None,
        track_module=True,
    )
    spec = util.spec_from_file_location(
        module_name,
        plugin_entrypoint_path,
        submodule_search_locations=[resolved_root],
    )
    if spec is None or spec.loader is None:
        raise ValidationError(f"Could not load plugin module for '{plugin_name}'.")
    module = util.module_from_spec(spec)
    sys.modules[module_name] = module
    loaded_plugin = False
    try:
        spec.loader.exec_module(module)
        try:
            plugin_class = module.Plugin
        except AttributeError as exception:
            raise ValidationError("Plugin module must expose a Plugin class.") from exception
        if not inspect.isclass(plugin_class) or not issubclass(plugin_class, BasePlugin):
            raise ValidationError("Plugin module must expose a BasePlugin subclass named Plugin.")
        ensure_declared_plugin_metadata(plugin_class, plugin_name=plugin_name)
        ensure_declared_openai_capability_flags(plugin_class, plugin_name=plugin_name)
        loaded_plugin = True
    finally:
        if not loaded_plugin:
            module_prefix = f"{module_name}."
            for loaded_name in tuple(sys.modules):
                if loaded_name == module_name or loaded_name.startswith(module_prefix):
                    sys.modules.pop(loaded_name, None)
    return plugin_class


def read_model_map(payload: JSONDict, key: str) -> dict[str, JSONDict] | None:
    value = payload.get(key)
    if value is None:
        return None
    model_map = require_json_object(
        value,
        label=f"Plugin worker payload '{key}'",
        build_error=ValidationError,
        invalid_message=f"Plugin worker payload '{key}' must be a JSON object.",
    )
    return {
        name: require_json_object(
            item,
            label=f"Plugin worker payload '{key}.{name}'",
            build_error=ValidationError,
            invalid_message=f"Plugin worker payload '{key}' must contain only JSON objects.",
        )
        for name, item in model_map.items()
    }
