"""SoAI - Model discovery pass with per-plugin lifecycle ownership [backend/models/discovery/discovery_pass.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.plugins.protocols_lifecycle import (
    PluginDiscoveryOperationProtocol,
    PluginDiscoveryOwnershipProtocol,
)
from models.discovery.provider_bounded_execution import (
    DiscoveryPassCoordination,
    PluginCheckFailure,
    PluginCheckSuccess,
    PluginCheckUnchanged,
)
from models.discovery.provider_execution import (
    DiscoveryProviderContext,
    discover_plugin_models,
    run_plugin_precheck,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from models.discovery.provider_bounded_execution import PluginDiscoveryResult

    type ExistingModelsByPlugin = dict[str, dict[str, JSONDict]]

__all__ = ("DiscoveryPassContext", "run_discovery_pass")


@dataclass(frozen=True, slots=True)
class DiscoveryPassContext:
    ownership: PluginDiscoveryOwnershipProtocol
    lock_timeout_seconds: float | None
    provider: DiscoveryProviderContext
    load_existing_models: Callable[[], Awaitable[ExistingModelsByPlugin]]
    reconcile: Callable[
        [dict[str, PluginDiscoveryResult], ExistingModelsByPlugin],
        Awaitable[None],
    ]


@dataclass(slots=True)
class _PluginDiscoveryRecord:
    plugin_name: str
    admitted: asyncio.Future[None] = field(
        default_factory=lambda: asyncio.get_running_loop().create_future(),
    )
    reported: asyncio.Event = field(default_factory=asyncio.Event)
    operation: PluginDiscoveryOperationProtocol | None = None
    result: PluginDiscoveryResult = None
    included: bool = False

    def report(self, result: PluginDiscoveryResult) -> None:
        self.result = result
        self.included = True
        self.reported.set()


def _resolve_pending(future: asyncio.Future[None]) -> None:
    if not future.done():
        future.set_result(None)


async def _run_plugin_operation(
    record: _PluginDiscoveryRecord,
    previous_admission: asyncio.Future[None] | None,
    coordination: DiscoveryPassCoordination,
    context: DiscoveryPassContext,
) -> None:
    precheck_settled = False
    try:
        if previous_admission is not None:
            await asyncio.shield(previous_admission)
        async with context.ownership.discovery_scope(
            record.plugin_name,
            timeout_seconds=context.lock_timeout_seconds,
        ) as operation:
            _resolve_pending(record.admitted)
            if operation is None:
                return
            record.operation = operation
            async with coordination.precheck_permits:
                plugin_check = await run_plugin_precheck(record.plugin_name, context.provider)
            precheck_settled = True
            coordination.settle_precheck()
            if plugin_check is None:
                return
            result: PluginDiscoveryResult
            if isinstance(plugin_check, PluginCheckSuccess):
                result = await discover_plugin_models(
                    plugin_check,
                    operation,
                    coordination,
                    context.provider.plugin_manager,
                )
            elif isinstance(plugin_check, PluginCheckFailure):
                result = plugin_check.error
            else:
                result = plugin_check
            record.report(result)
            if not isinstance(result, PluginCheckUnchanged):
                await operation.await_reconciliation()
    finally:
        _resolve_pending(record.admitted)
        if not precheck_settled:
            coordination.settle_precheck()
        record.reported.set()


def _freeze_discovered_data(
    records: list[_PluginDiscoveryRecord],
) -> dict[str, PluginDiscoveryResult]:
    discovered_data: dict[str, PluginDiscoveryResult] = {}
    for record in records:
        if not record.included or record.operation is None:
            continue
        result = record.result
        if not isinstance(result, PluginCheckUnchanged) and not record.operation.freeze():
            result = PluginCheckUnchanged(plugin_name=record.plugin_name)
        discovered_data[record.plugin_name] = result
    return discovered_data


async def _raise_for_terminated_operations(tasks: list[asyncio.Task[None]]) -> None:
    for task in tasks:
        if task.done() and (task.cancelled() or task.exception() is not None):
            await task


async def run_discovery_pass(plugin_names: set[str], context: DiscoveryPassContext) -> bool:
    records = [_PluginDiscoveryRecord(plugin_name) for plugin_name in sorted(plugin_names)]
    coordination = DiscoveryPassCoordination(pending_prechecks=len(records))
    tasks: list[asyncio.Task[None]] = []
    admitted = False
    completed = False
    try:
        previous_admission: asyncio.Future[None] | None = None
        for record in records:
            tasks.append(
                create_ephemeral_task(
                    _run_plugin_operation(record, previous_admission, coordination, context),
                    name=f"model-discovery-{record.plugin_name}",
                ),
            )
            previous_admission = record.admitted
        await coordination.prechecks_settled.wait()
        await _raise_for_terminated_operations(tasks)
        admitted = any(record.operation is not None for record in records)
        if admitted:
            existing_models = await context.load_existing_models()
            coordination.open_provider_phase(existing_models)
            for record in records:
                await record.reported.wait()
            await _raise_for_terminated_operations(tasks)
            await context.reconcile(_freeze_discovered_data(records), existing_models)
        completed = True
    finally:
        for record in records:
            if record.operation is not None:
                record.operation.settle()
        if completed:
            await asyncio.gather(*tasks, return_exceptions=False)
        else:
            await uncancel_then_cleanup(cancel_and_await(tasks, task_label="model discovery"))
    return admitted
