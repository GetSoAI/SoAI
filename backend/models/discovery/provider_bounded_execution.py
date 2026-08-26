"""SoAI - Bounded model discovery provider task scheduling [backend/models/discovery/provider_bounded_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.timing.monotonic import monotonic_ms
from core.types.json import JSONDict

__all__ = (
    "PluginCheckFailure",
    "PluginCheckSuccess",
    "PluginCheckUnchanged",
    "run_bounded_discovery_calls",
    "run_bounded_plugin_checks",
)

LOGGER_NAME = "SoAI.models.discovery.provider_bounded_execution"
OPERATION_MODEL_DISCOVERY_RUN_DISCOVERY_PROVIDERS_DISCOVER_PLUGIN = (
    "model_discovery.run_discovery_providers.discover_plugin"
)


@dataclass(frozen=True, slots=True)
class PluginCheckSuccess:
    plugin_name: str
    instance: PluginInstanceProtocol
    loaded_for_discovery: bool


@dataclass(frozen=True, slots=True)
class PluginCheckFailure:
    plugin_name: str
    error: Exception


@dataclass(frozen=True, slots=True)
class PluginCheckUnchanged:
    plugin_name: str


async def run_bounded_plugin_checks(
    plugin_names: list[str],
    check_plugin: Callable[
        [str],
        Awaitable[PluginCheckSuccess | PluginCheckFailure | PluginCheckUnchanged | None],
    ],
    concurrency_limit: int,
) -> list[PluginCheckSuccess | PluginCheckFailure | PluginCheckUnchanged | None]:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    for plugin_name in plugin_names:
        queue.put_nowait(plugin_name)
    worker_count = min(max(1, concurrency_limit), max(1, len(plugin_names)))
    for _index in range(worker_count):
        queue.put_nowait(None)
    results: list[PluginCheckSuccess | PluginCheckFailure | PluginCheckUnchanged | None] = []
    results_lock = asyncio.Lock()

    async def worker() -> None:
        while True:
            plugin_name = await queue.get()
            if plugin_name is None:
                return
            started_ms = monotonic_ms()
            result = await check_plugin(plugin_name)
            duration_ms = monotonic_ms() - started_ms
            get_logger(LOGGER_NAME).debug(
                "Model discovery pre-check for plugin '%s' completed in %sms.",
                plugin_name,
                duration_ms,
            )
            async with results_lock:
                results.append(result)

    worker_tasks = [worker() for _index in range(worker_count)]
    await asyncio.gather(*worker_tasks, return_exceptions=False)
    return results


async def run_bounded_discovery_calls(
    plugin_instances: dict[str, PluginInstanceProtocol],
    discover_models: Callable[[str, PluginInstanceProtocol], Awaitable[dict[str, JSONDict] | None]],
    concurrency_limit: int,
) -> list[dict[str, JSONDict] | Exception | None]:
    queue: asyncio.Queue[tuple[str, PluginInstanceProtocol] | None] = asyncio.Queue()
    for item in plugin_instances.items():
        queue.put_nowait(item)
    worker_count = min(max(1, concurrency_limit), max(1, len(plugin_instances)))
    for _index in range(worker_count):
        queue.put_nowait(None)
    results: dict[str, dict[str, JSONDict] | Exception | None] = {}
    results_lock = asyncio.Lock()
    logger = get_logger(LOGGER_NAME)

    async def worker() -> None:
        while True:
            item = await queue.get()
            if item is None:
                return
            plugin_name, instance = item
            result: dict[str, JSONDict] | Exception | None
            started_ms = monotonic_ms()
            try:
                result = await discover_models(plugin_name, instance)
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                result = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_MODEL_DISCOVERY_RUN_DISCOVERY_PROVIDERS_DISCOVER_PLUGIN,
                )
                log_exception(
                    logger,
                    result,
                    message="Model discovery plugin call failed.",
                    operation=OPERATION_MODEL_DISCOVERY_RUN_DISCOVERY_PROVIDERS_DISCOVER_PLUGIN,
                    details={"plugin_name": plugin_name},
                )
            duration_ms = monotonic_ms() - started_ms
            logger.debug(
                "Model discovery provider '%s' completed in %sms.",
                plugin_name,
                duration_ms,
            )
            async with results_lock:
                results[plugin_name] = result

    worker_tasks = [worker() for _index in range(worker_count)]
    await asyncio.gather(*worker_tasks, return_exceptions=False)
    return [results[plugin_name] for plugin_name in plugin_instances]
