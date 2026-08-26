"""SoAI - Model discovery startup phase resolution [backend/models/discovery/startup_phase.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.runtime.startup_status import StartupPhaseResult, StartupPhaseStatus

__all__ = ("resolve_plugin_reconciliation_startup_blocker",)


def resolve_plugin_reconciliation_startup_blocker(
    plugin_result: StartupPhaseResult,
) -> StartupPhaseResult | None:
    if plugin_result.status is StartupPhaseStatus.SUCCESS:
        return None
    if plugin_result.status is StartupPhaseStatus.CANCELLED_BY_SHUTDOWN:
        return StartupPhaseResult(StartupPhaseStatus.CANCELLED_BY_SHUTDOWN)
    if plugin_result.status is StartupPhaseStatus.FAILED:
        return StartupPhaseResult(
            StartupPhaseStatus.FAILED,
            plugin_result.message,
        )
    return StartupPhaseResult(
        StartupPhaseStatus.FAILED,
        f"Plugin reconciliation completed with unexpected status: {plugin_result.status}",
    )
