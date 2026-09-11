"""SoAI - Bootstrap resource cleanup entry construction [backend/app/composition/bootstrap_resource_cleanup_entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.lifecycle.database_shutdown_entries import database_shutdown_entries
from app.lifecycle.entries import LifecycleEntry

if TYPE_CHECKING:
    import httpx2

    from app.types_services_database import DatabaseServices
    from core.events.protocols import EventBusProtocol
    from core.lifecycle.protocols import Shutdownable

__all__ = ("bootstrap_resource_cleanup_entries",)


def bootstrap_resource_cleanup_entries(
    *,
    phase: str,
    timeout_sec: float,
    task_registry: Shutdownable | None,
    config_manager: Shutdownable | None,
    http_client: httpx2.AsyncClient | None,
    database_services: DatabaseServices | None,
    event_bus: EventBusProtocol | None = None,
) -> tuple[LifecycleEntry, ...]:
    entries: list[LifecycleEntry] = []
    _append_shutdown_entry(
        entries,
        component_name="Bootstrap Task Registry",
        phase=phase,
        action_target=task_registry,
        timeout_sec=timeout_sec,
    )
    _append_shutdown_entry(
        entries,
        component_name="Bootstrap Config Manager",
        phase=phase,
        action_target=config_manager,
        timeout_sec=timeout_sec,
    )
    if http_client is not None:
        entries.append(
            LifecycleEntry(
                component_name="Bootstrap HTTP Client",
                phase=phase,
                action=http_client.aclose,
                timeout_sec=timeout_sec,
                critical=False,
            ),
        )
    if database_services is not None:
        entries.extend(
            database_shutdown_entries(
                database_core=database_services.core,
                phase=phase,
                timeout_sec=timeout_sec,
                critical=False,
            ),
        )
    _append_shutdown_entry(
        entries,
        component_name="Bootstrap Event Bus",
        phase=phase,
        action_target=event_bus,
        timeout_sec=timeout_sec,
    )
    return tuple(entries)


def _append_shutdown_entry(
    entries: list[LifecycleEntry],
    *,
    component_name: str,
    phase: str,
    action_target: Shutdownable | None,
    timeout_sec: float,
) -> None:
    if action_target is None:
        return
    entries.append(
        LifecycleEntry(
            component_name=component_name,
            phase=phase,
            action=action_target.shutdown,
            timeout_sec=timeout_sec,
            critical=False,
        ),
    )
