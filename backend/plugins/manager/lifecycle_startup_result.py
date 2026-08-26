"""SoAI - Plugin manager startup reconciliation result state [backend/plugins/manager/lifecycle_startup_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.runtime.startup_status import StartupPhaseResult, StartupPhaseStatus

if TYPE_CHECKING:
    from plugins.manager.internal_protocols import PluginManagerLifecycleTarget

__all__ = (
    "mark_initial_reconciliation_cancelled_by_shutdown",
    "mark_initial_reconciliation_failed",
    "mark_initial_reconciliation_success",
    "raise_for_initial_reconciliation_failure",
)


def mark_initial_reconciliation_success(manager: PluginManagerLifecycleTarget) -> None:
    manager.state.lifecycle.initial_reconciliation_error = None
    manager.state.lifecycle.initial_reconciliation_result = StartupPhaseResult(
        StartupPhaseStatus.SUCCESS,
    )
    if manager.state.lifecycle.fatal_readiness_error is None:
        manager.state.lifecycle.readiness_degraded_published = False


def mark_initial_reconciliation_failed(
    manager: PluginManagerLifecycleTarget,
    message: str,
) -> None:
    manager.state.lifecycle.initial_reconciliation_error = message
    manager.state.lifecycle.initial_reconciliation_result = StartupPhaseResult(
        StartupPhaseStatus.FAILED,
        message,
    )


def mark_initial_reconciliation_cancelled_by_shutdown(
    manager: PluginManagerLifecycleTarget,
) -> None:
    manager.state.lifecycle.initial_reconciliation_result = StartupPhaseResult(
        StartupPhaseStatus.CANCELLED_BY_SHUTDOWN,
    )


def raise_for_initial_reconciliation_failure(
    manager: PluginManagerLifecycleTarget,
) -> None:
    result = manager.state.lifecycle.initial_reconciliation_result
    if result.status is StartupPhaseStatus.FAILED:
        raise StateError(
            "Plugin manager startup reconciliation failed.",
            operation="plugin_manager.require_ready",
            details={"reconciliation_result": result.message},
        )
    if result.status is StartupPhaseStatus.CANCELLED_BY_SHUTDOWN:
        raise StateError(
            "Plugin manager startup reconciliation was cancelled by shutdown.",
            operation="plugin_manager.require_ready",
        )
    if result.status is StartupPhaseStatus.PENDING:
        raise StateError(
            "Plugin manager startup reconciliation completed without a terminal result.",
            operation="plugin_manager.require_ready",
        )
    if result.status is not StartupPhaseStatus.SUCCESS:
        raise StateError(
            "Plugin manager startup reconciliation completed with an unknown result.",
            operation="plugin_manager.require_ready",
        )
