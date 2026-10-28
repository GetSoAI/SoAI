"""SoAI - SoAIBench hardware history reset [backend/hardware/soaibench/history_reset.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.types_system import HardwareHistoryResetEvent
from core.history.reset_notification import (
    HistoryResetOutcome,
    publish_committed_history_reset,
)
from hardware.soaibench.service_cancellation import cancel_active_soaibench_runs

if TYPE_CHECKING:
    from core.concurrency.locks import AsyncRWLock
    from hardware.soaibench.active_runs import ActiveSoAIBenchRuns
    from hardware.soaibench.dependencies import SoAIBenchServiceDependencies

__all__ = ("reset_soaibench_history",)

HISTORY_RESET_OPERATION = "hardware.soaibench.history_reset"


async def reset_soaibench_history(
    *,
    deps: SoAIBenchServiceDependencies,
    active_runs: ActiveSoAIBenchRuns,
    history_reset_lock: AsyncRWLock,
    reset_genesis_uptime: bool,
) -> HistoryResetOutcome:
    async with history_reset_lock.write_lock():
        await cancel_active_soaibench_runs(
            deps=deps,
            active_runs=active_runs,
            reason="SoAI Bench history reset",
            operation=HISTORY_RESET_OPERATION,
            cancelled_message="SoAI Bench worker cancelled during history reset.",
        )
        cleared_through_ms = await deps.database_hardware.clear_hardware_history(
            reset_genesis_uptime,
        )
    return await publish_committed_history_reset(
        event_bus=deps.event_bus,
        event=HardwareHistoryResetEvent(cleared_through_ms=cleared_through_ms),
        logger=deps.logger,
        operation=HISTORY_RESET_OPERATION,
    )
