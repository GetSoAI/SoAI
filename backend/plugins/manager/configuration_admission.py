"""SoAI - Serialized plugin configuration admission and commit [backend/plugins/manager/configuration_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from ruamel.yaml.comments import CommentedMap

from core.config.gpu_binding import (
    GPU_BINDING_CONFIG_KEY,
    normalize_gpu_binding_config,
    normalize_gpu_binding_runtime_family,
)
from core.config.gpu_binding_devices import (
    validate_gpu_binding_device_ids,
    validate_gpu_binding_runtime,
)
from core.config.merge import deep_merge_config
from core.errors.exceptions import (
    ConfigurationError,
    ConflictError,
    ServiceUnavailableError,
    SoAIError,
    StateError,
    ValidationError,
)
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.plugins.backend_variant_status import (
    read_installed_backend_variant_id,
    status_reports_installed_backend,
)
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.serialization.json import normalize_for_json
from core.types.dict import freeze_json_dict
from core.types.json import JSONDict, is_json_dict
from plugins.lifecycle_advisory_lock import plugin_lifecycle_advisory_lock
from plugins.manager.backend_variant_compatibility import (
    snapshot_backend_compatibility_observations,
)
from plugins.manager.backend_variant_option_loading import load_backend_variant_options
from plugins.manager.capabilities import ensure_plugin_capability
from plugins.manager.configuration import (
    get_plugin_configuration,
    refresh_plugin_runtime_configuration,
)
from plugins.manager.load_serialization import serialized_plugin_load_scope
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

if TYPE_CHECKING:
    from core.config.gpu_binding import GpuBindingRuntimeFamily

__all__ = ("patch_plugin_configuration",)

RUNTIME_APPLICATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    SoAIError,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
)


async def patch_plugin_configuration(
    manager: PluginManagerRuntimeProtocol, plugin_name: str, changes: JSONDict
) -> None:
    manager.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
    async with plugin_lifecycle_advisory_lock(manager, plugin_name):
        async with serialized_plugin_load_scope(manager, plugin_name):
            current = freeze_json_dict(await get_plugin_configuration(manager, plugin_name))
            instance = await manager.get_plugin_instance(plugin_name)
            proposed_changes = dict(changes)
            binding_changed = GPU_BINDING_CONFIG_KEY in proposed_changes
            if binding_changed:
                proposed_changes[GPU_BINDING_CONFIG_KEY] = normalize_gpu_binding_config(
                    proposed_changes[GPU_BINDING_CONFIG_KEY]
                )
                binding_changed = (
                    current.get(GPU_BINDING_CONFIG_KEY) != proposed_changes[GPU_BINDING_CONFIG_KEY]
                )
            proposed_value = normalize_for_json(
                deep_merge_config(dict(current), proposed_changes, expand_dots=False)
            )
            if not is_json_dict(proposed_value):
                raise ValidationError("Proposed plugin configuration is not a mapping.")
            proposed = freeze_json_dict(proposed_value)
            capabilities, inventory = freeze_json_dict({}), None
            if instance is not None or binding_changed:
                capabilities, inventory = await snapshot_backend_compatibility_observations(
                    manager, plugin_name
                )
            if binding_changed:
                await _validate_execution_binding(
                    manager,
                    plugin_name,
                    instance,
                    proposed_value,
                    dict(inventory) if inventory is not None else None,
                )
            if instance is not None:
                await instance.validate_runtime_configuration(
                    current, proposed, capabilities, inventory
                )

            def updater(persisted: CommentedMap) -> CommentedMap:
                if normalize_for_json(persisted) != dict(current):
                    error = ConflictError(
                        "The plugin configuration changed. Refresh it and review your changes before saving again."
                    )
                    apply_public_error_payload(
                        error,
                        ErrorPublicPayload(
                            code="plugin_configuration_changed",
                            message=error.message,
                            http_status=409,
                            details={"reason": "configuration_changed"},
                        ),
                    )
                    raise error
                merged = deep_merge_config(persisted, proposed_changes, expand_dots=False)
                return merged if isinstance(merged, CommentedMap) else CommentedMap(merged)

            saved = await manager.dependencies.infrastructure.config_manager.update_config_transactionally(
                plugin_name, source="api:config_patch", updater=updater, changed_keys=None
            )
            if not saved:
                raise ConfigurationError("The plugin configuration could not be saved.")
    try:
        await refresh_plugin_runtime_configuration(manager, plugin_name, auto_load=False)
    except RUNTIME_APPLICATION_EXCEPTIONS as exception:
        error = StateError(
            "The configuration was saved, but the runtime could not apply it. Review the backend status and retry applying the configuration.",
            cause=exception,
        )
        apply_public_error_payload(
            error,
            ErrorPublicPayload(
                code="plugin_configuration_apply_failed",
                message=error.message,
                http_status=500,
                details={"configuration_saved": True},
            ),
        )
        raise error from exception


async def _validate_execution_binding(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    instance: PluginInstanceProtocol | None,
    proposed: JSONDict,
    inventory: JSONDict | None,
) -> None:
    if instance is None:
        await ensure_plugin_capability(manager, plugin_name, "SUPPORTS_GPU_BINDING", "GPU Binding")
    else:
        manager.require_plugin_capability(instance, "SUPPORTS_GPU_BINDING", "GPU Binding")
    binding = normalize_gpu_binding_config(proposed.get(GPU_BINDING_CONFIG_KEY))
    if binding.get("mode") != "selected":
        return
    if inventory is None:
        error = ServiceUnavailableError(
            "GPU information is unavailable. Refresh the hardware information before changing selected GPUs."
        )
        apply_public_error_payload(
            error,
            ErrorPublicPayload(
                code="gpu_observation_unavailable", message=error.message, http_status=503
            ),
        )
        raise error
    selected_variant = await manager.dependencies.databases.plugins.get_backend_variant_id(
        plugin_name
    )
    options = await load_backend_variant_options(manager, plugin_name)
    runtime_family: GpuBindingRuntimeFamily | None = next(
        (
            normalize_gpu_binding_runtime_family(option.get("gpu_binding_runtime_family"))
            for option in options
            if option.get("id") == selected_variant
        ),
        None,
    )
    if runtime_family is None and instance is not None:
        status = await instance.get_status()
        if status_reports_installed_backend(status):
            runtime_family = normalize_gpu_binding_runtime_family(
                status.get("gpu_binding_runtime_family")
            )
            if runtime_family is None:
                runtime_family = normalize_gpu_binding_runtime_family(
                    read_installed_backend_variant_id(status)
                )
    if runtime_family is None:
        validate_gpu_binding_device_ids(binding, inventory)
    else:
        validate_gpu_binding_runtime(binding, inventory, runtime_family)
