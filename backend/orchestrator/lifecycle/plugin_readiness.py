"""SoAI - Orchestrator lifecycle plugin readiness checks [backend/orchestrator/lifecycle/plugin_readiness.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.timing.constants import MODERATE_DELAY_SEC

__all__ = ("wait_for_plugin_ready",)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.plugin_readiness"
OPERATION = "orchestrator_lifecycle.wait_for_plugin_ready"


async def wait_for_plugin_ready(
    plugin_instance: PluginInstanceProtocol,
    shutdown_event: asyncio.Event,
    timeout: float,
    *,
    require_live_backend_process: bool,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    deadline = deadline_after(timeout)
    while not deadline.expired():
        if shutdown_event.is_set():
            return False
        remaining = deadline.remaining_seconds()
        probe_timeout = min(5.0, remaining)
        try:
            healthy, _ = await asyncio.wait_for(
                plugin_instance.health_ping(),
                timeout=probe_timeout,
            )
            if healthy:
                return True
            if require_live_backend_process:
                backend_process_pids = await asyncio.wait_for(
                    plugin_instance.get_backend_process_pids(),
                    timeout=probe_timeout,
                )
                if not backend_process_pids:
                    logger.error(
                        "Tracked backend process exited while plugin '%s' was becoming ready.",
                        plugin_instance.plugin_name,
                    )
                    return False
        except TimeoutError as exception:
            plugin_instance_name = plugin_instance.plugin_name
            log_handled_exception(
                logger,
                exception,
                message="Health ping timed out while waiting for plugin readiness (non-critical).",
                operation=OPERATION,
                details={"plugin": plugin_instance_name},
                level="debug",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            plugin_instance_name = plugin_instance.plugin_name
            log_exception(
                logger,
                exception,
                message="Health ping failed while waiting for plugin readiness",
                operation=OPERATION,
                details={"plugin": plugin_instance_name},
                level="warning",
            )
        await asyncio.sleep(MODERATE_DELAY_SEC)
    return False
