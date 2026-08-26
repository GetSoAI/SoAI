"""SoAI - Prefetch plugin instances for guardian checks [backend/plugins/guardian_checks/plugin_instance_prefetch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from core.plugins.protocols_instance import PluginInstanceProtocol
from plugins.guardian.eligibility import GUARDIAN_LOGGER_NAME
from plugins.protocols_internal.guardian.internal_protocols import (
    PluginGuardianInternalProtocol,
)

__all__ = ("prefetch_plugin_instances",)

OPERATION_PLUGINS_GUARDIAN_CHECKS_PLUGIN_INSTANCE_PREFETCH_PREFETCH_PLUGIN_INSTANCES = (
    "plugins.guardian_checks.plugin_instance_prefetch.prefetch_plugin_instances"
)


async def prefetch_plugin_instances(
    self: PluginGuardianInternalProtocol,
    plugin_names: list[str],
    *,
    operation: str,
) -> dict[str, PluginInstanceProtocol]:
    logger = get_logger(GUARDIAN_LOGGER_NAME)
    prefetch_tasks = [self.plugin_manager.get_plugin_instance(name) for name in plugin_names]
    raw_instances = await asyncio.gather(
        *prefetch_tasks,
        return_exceptions=True,
    )
    instances: dict[str, PluginInstanceProtocol] = {}
    for name, instance in zip(plugin_names, raw_instances, strict=True):
        if isinstance(instance, BaseException):
            log_exception(
                logger,
                instance,
                message=f"Failed to prefetch plugin instance for '{name}'",
                operation=OPERATION_PLUGINS_GUARDIAN_CHECKS_PLUGIN_INSTANCE_PREFETCH_PREFETCH_PLUGIN_INSTANCES,
                details={"plugin_name": name, "operation": operation},
                level="warning",
            )
            continue
        if instance is not None:
            instances[name] = instance
    return instances
