"""SoAI - Application component shutdown sequence [backend/app/shutdown_components.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.lifecycle.budgets import LifecycleShutdownBudgets
from app.lifecycle.failure_recording import record_critical_lifecycle_failures
from app.lifecycle.runner import LifecycleRunner
from app.lifecycle.shutdown_service_plan import build_service_shutdown_entries
from app.types_application import ApplicationContext
from core.logging.protocols import LoggerProtocol

__all__ = ("shutdown_components",)


async def shutdown_components(
    *,
    application_context: ApplicationContext,
    logger: LoggerProtocol,
    budgets: LifecycleShutdownBudgets,
) -> None:
    entries = build_service_shutdown_entries(
        application_context,
        component_timeout_sec=budgets.component_timeout_sec,
        task_registry_timeout_sec=budgets.task_registry_timeout_sec,
        orchestrator_timeout_sec=budgets.orchestrator_timeout_sec,
        mcp_timeout_sec=budgets.mcp_timeout_sec,
    )
    failures = await LifecycleRunner(logger=logger).run_entries_continue(entries)
    record_critical_lifecycle_failures(application_context, failures)
