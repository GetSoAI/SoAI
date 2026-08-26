"""SoAI - Reconciled plugin catalog state finalization [backend/plugins/registry/reconciled_catalog_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.events.completion_waiting import await_publication_receipt
from core.state.state_names import (
    PLUGIN_STATE_ABSENT,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_PERSISTENT_READY,
    PLUGIN_STATE_STOPPED,
)
from core.validation.boolean_coercion import coerce_bool_with_recovery
from plugins.manager.backend_variant_counts import persist_backend_variant_count_without_event
from plugins.manager.backend_variant_option_loading import load_backend_variant_options

if TYPE_CHECKING:
    from core.state.protocols import AuthoritativePluginStateTransitionReceipt
    from core.state.state_names import PluginRuntimeStateName
    from core.types.json import JSONDict
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("finalize_reconciled_catalog_states",)

OPERATION = "plugins.registry.reconciled_catalog_state"
RECONCILABLE_CATALOG_STATES: frozenset[PluginRuntimeStateName] = frozenset(
    (PLUGIN_STATE_NOT_DETECTED, PLUGIN_STATE_ABSENT),
)


def _read_manifest_bool(
    manager: PluginManagerRuntimeProtocol,
    plugin_record: JSONDict,
    field_name: str,
) -> bool:
    return coerce_bool_with_recovery(
        plugin_record,
        field_name,
        logger=manager.logger,
        operation=OPERATION,
        default=False,
    )


def _has_incompatibility(plugin_record: JSONDict) -> bool:
    reason = plugin_record.get("incompatibility_reason")
    return isinstance(reason, str) and bool(reason.strip())


def _resolve_catalog_state(
    manager: PluginManagerRuntimeProtocol,
    plugin_record: JSONDict,
) -> PluginRuntimeStateName | None:
    current_state = plugin_record.get("state")
    if current_state not in RECONCILABLE_CATALOG_STATES:
        return None
    if _has_incompatibility(plugin_record):
        return None
    supports_backend_installation = _read_manifest_bool(
        manager,
        plugin_record,
        "supports_backend_installation",
    )
    if supports_backend_installation:
        return PLUGIN_STATE_BACKEND_NOT_INSTALLED
    if _read_manifest_bool(manager, plugin_record, "persistent"):
        return PLUGIN_STATE_PERSISTENT_READY
    return PLUGIN_STATE_STOPPED


async def _persist_variant_count_for_state(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    state: PluginRuntimeStateName,
) -> None:
    if state != PLUGIN_STATE_BACKEND_NOT_INSTALLED:
        return
    options = await load_backend_variant_options(manager, plugin_name)
    await persist_backend_variant_count_without_event(manager, plugin_name, state, options)


async def _can_finalize_authoritative_state(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> bool:
    state = await manager.dependencies.infrastructure.state_aggregator.get_plugin_status(
        plugin_name,
    )
    return state in RECONCILABLE_CATALOG_STATES


async def _wait_for_transition_receipts(
    receipts: list[AuthoritativePluginStateTransitionReceipt],
) -> None:
    if not receipts:
        return
    receipt_wait_tasks = [await_publication_receipt(receipt) for receipt in receipts]
    await asyncio.gather(*receipt_wait_tasks, return_exceptions=False)


async def finalize_reconciled_catalog_states(
    manager: PluginManagerRuntimeProtocol,
    plugin_names: set[str],
) -> None:
    receipts: list[AuthoritativePluginStateTransitionReceipt] = []
    try:
        for plugin_name in sorted(plugin_names):
            plugin_record = await manager.dependencies.databases.plugins.get_plugin_by_name(
                plugin_name,
            )
            if plugin_record is None:
                continue
            target_state = _resolve_catalog_state(manager, plugin_record)
            if target_state is None:
                continue
            if not await _can_finalize_authoritative_state(manager, plugin_name):
                continue
            receipt = await manager.transition_plugin_manager_state(
                plugin_name,
                target_state,
                "Catalog reconciliation finalized plugin availability.",
            )
            if receipt is not None:
                receipts.append(receipt)
            await _persist_variant_count_for_state(manager, plugin_name, target_state)
    finally:
        await _wait_for_transition_receipts(receipts)
