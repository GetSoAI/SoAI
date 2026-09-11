"""SoAI - Plugin instance loading and reload coordination [backend/plugins/manager/instance_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.plugins.protocols_instance import PluginInstanceProtocol
from plugins.artifact_paths import get_plugin_file_hash
from plugins.loader.loading import load_and_announce_plugin
from plugins.loader.loading_policy import PluginLoadOutcome, PluginLoadPolicy
from plugins.loader.preflight import (
    PluginPreflightResult,
    perform_plugin_preflight_checks,
)
from plugins.manager.artifacts import teardown_plugin_runtime
from plugins.manager.compatibility import ensure_record_is_compatible
from plugins.manager.instances import get_plugin_instance
from plugins.manager.load_serialization import serialized_plugin_load_scope
from plugins.path_safety import get_plugin_file_path
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "load_plugin_instance",
    "load_plugin_activation",
    "reload_plugin_instance",
    "require_loaded_plugin",
)

LOGGER_NAME = "SoAI.plugins.manager.instance_loading"
OPERATION = "plugins.require_loaded_plugin"


async def load_plugin_instance(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    force_reload: bool,
    already_serialized: bool = False,
    preflight_result: PluginPreflightResult | None = None,
) -> PluginInstanceProtocol:
    async def _load_under_lock() -> PluginInstanceProtocol:
        resolved_preflight_result = preflight_result
        if force_reload:
            if resolved_preflight_result is None:
                resolved_preflight_result = await perform_plugin_preflight_checks(
                    self,
                    plugin_name,
                )
            await teardown_plugin_runtime(
                self,
                plugin_name,
                clear_display_name_cache=False,
                update_aliases=False,
            )
        outcome = await load_and_announce_plugin(
            self,
            plugin_name,
            force_reload=force_reload,
            preflight_result=resolved_preflight_result,
        )
        return outcome.instance

    if already_serialized:
        return await _load_under_lock()
    async with serialized_plugin_load_scope(self, plugin_name):
        return await _load_under_lock()


async def load_plugin_activation(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    policy: PluginLoadPolicy,
    already_serialized: bool,
) -> PluginLoadOutcome:
    async def _load_under_lock() -> PluginLoadOutcome:
        preflight_result = await perform_plugin_preflight_checks(self, plugin_name)
        await teardown_plugin_runtime(
            self,
            plugin_name,
            clear_display_name_cache=False,
            update_aliases=False,
        )
        return await load_and_announce_plugin(
            self,
            plugin_name,
            force_reload=True,
            preflight_result=preflight_result,
            policy=policy,
        )

    if already_serialized:
        return await _load_under_lock()
    async with serialized_plugin_load_scope(self, plugin_name):
        return await _load_under_lock()


async def require_loaded_plugin(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    display_name: str | None = None,
    auto_load: bool = False,
    *,
    already_serialized: bool = False,
) -> PluginInstanceProtocol:
    logger = get_logger(LOGGER_NAME)
    instance = await get_plugin_instance(self, plugin_name)
    if auto_load:
        plugin_record = await self.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
        ensure_record_is_compatible(self, plugin_name, plugin_record)
        plugin_file_path = get_plugin_file_path(self, plugin_name)
        if not (
            current_hash := await get_plugin_file_hash(
                self,
                plugin_name,
                plugin_file_path=plugin_file_path,
            )
        ):
            raise NotFoundError(
                f"Could not get hash for plugin file at {plugin_file_path}. It may not exist.",
            )
        async with self.state.locks.load_lock:
            loaded_surface_info = self.state.catalog.loaded_plugin_surfaces.get(plugin_name)
            instance_check = self.state.catalog.loaded_plugin_instances.get(plugin_name)
        should_load = instance is None or not loaded_surface_info or not instance_check
        should_reload = (
            loaded_surface_info is not None
            and instance_check is not None
            and loaded_surface_info[1] != current_hash
        )
        if should_load or should_reload:
            if loaded_surface_info and loaded_surface_info[1] != current_hash:
                logger.warning(
                    "Plugin file for '%s' has changed on disk. Forcing a reload.",
                    plugin_name,
                )
            try:
                await load_plugin_instance(
                    self,
                    plugin_name,
                    force_reload=should_reload or instance is not None,
                    already_serialized=already_serialized,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                trace_id = f"sys_plugin_load_failed_{plugin_name}_{uuid.uuid4().hex[:12]}"
                coerced = coerce_to_soai_error(
                    exception,
                    operation="plugins.require_loaded_plugin",
                )
                log_exception(
                    logger,
                    coerced,
                    message=f"Failed to load plugin '{plugin_name}'.",
                    trace_id=trace_id,
                    operation=OPERATION,
                    details={"plugin": plugin_name},
                )
                raise StateError(f"Failed to load plugin '{plugin_name}'.") from exception
            instance = await get_plugin_instance(self, plugin_name)
        if not instance:
            plugin_record = (
                plugin_record
                or await self.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
            )
            ensure_record_is_compatible(self, plugin_name, plugin_record)
        if not instance:
            raise StateError(
                f"Failed to get a valid instance of '{plugin_name}' after load/reload attempt.",
            )
    if instance is None:
        raise ValidationError(
            f"Plugin '{display_name or plugin_name}' is not loaded or does not exist.",
        )
    return instance


async def reload_plugin_instance(self: PluginManagerRuntimeProtocol, plugin_name: str) -> None:
    await load_plugin_instance(self, plugin_name, force_reload=True)
