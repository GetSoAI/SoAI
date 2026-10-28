"""SoAI - Shutdown infrastructure lifecycle plan construction [backend/app/lifecycle/shutdown_infrastructure_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import get_running_loop
from typing import TYPE_CHECKING

from app.lifecycle.database_shutdown_entries import database_shutdown_entries
from app.lifecycle.entries import LifecycleEntry
from core.errors.exceptions import ValidationError
from core.validation.strict_numbers import require_finite_float_strict

if TYPE_CHECKING:
    from app.types_application import ApplicationContext

__all__ = (
    "build_event_bus_shutdown_entries",
    "build_hardware_shutdown_entries",
    "build_http_client_and_database_shutdown_entries",
    "build_pre_shutdown_quiesce_entries",
)


def build_pre_shutdown_quiesce_entries(
    application_context: ApplicationContext,
    *,
    component_timeout_sec: float,
) -> tuple[LifecycleEntry, ...]:
    return (
        LifecycleEntry(
            component_name="Licensing Recovery Actor",
            phase="pre_shutdown_quiesce",
            action=application_context.services.licensing.recovery_actor.shutdown,
            timeout_sec=component_timeout_sec,
            critical=False,
        ),
        LifecycleEntry(
            component_name="Communications Sync Actor",
            phase="pre_shutdown_quiesce",
            action=application_context.services.infrastructure.communications.sync_actor.shutdown,
            timeout_sec=component_timeout_sec,
            critical=False,
        ),
    )


def build_event_bus_shutdown_entries(
    application_context: ApplicationContext,
    *,
    component_timeout_sec: float,
) -> tuple[LifecycleEntry, ...]:
    return (
        LifecycleEntry(
            component_name="Event Bus",
            phase="shutdown",
            action=application_context.services.infrastructure.event_bus.shutdown,
            timeout_sec=component_timeout_sec,
            critical=True,
        ),
    )


def build_http_client_and_database_shutdown_entries(
    application_context: ApplicationContext,
    *,
    component_timeout_sec: float,
) -> tuple[LifecycleEntry, ...]:
    return (
        LifecycleEntry(
            component_name="Licensing Authority HTTP Client",
            phase="shutdown",
            action=application_context.services.licensing.authority_http_client.aclose,
            timeout_sec=component_timeout_sec,
            critical=True,
        ),
        LifecycleEntry(
            component_name="HTTP Client",
            phase="shutdown",
            action=application_context.services.infrastructure.http_client.aclose,
            timeout_sec=component_timeout_sec,
            critical=True,
        ),
        *database_shutdown_entries(
            database_core=application_context.services.databases.core,
            phase="shutdown",
            timeout_sec=component_timeout_sec,
            critical=True,
        ),
    )


def build_hardware_shutdown_entries(
    application_context: ApplicationContext,
    *,
    component_timeout_sec: float,
) -> tuple[LifecycleEntry, ...]:
    budget = require_finite_float_strict(
        component_timeout_sec, error_message="GPU shutdown budget must be finite."
    )
    if budget < 0:
        raise ValidationError("GPU shutdown budget must be nonnegative.")

    async def clear_hardware_dirty_flag() -> None:
        await application_context.services.infrastructure.hardware.gpu_tuning.clear_dirty_shutdown_flag(
            deadline_monotonic=get_running_loop().time() + budget
        )

    return (
        LifecycleEntry(
            component_name="Hardware Dirty Shutdown Flag",
            phase="shutdown",
            action=clear_hardware_dirty_flag,
            timeout_sec=component_timeout_sec,
            critical=False,
        ),
    )
