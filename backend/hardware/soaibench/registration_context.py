"""SoAI - SoAIBench worker registration context [backend/hardware/soaibench/registration_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallActivity
    from core.types.json import JSONDict
    from hardware.soaibench.active_runs import ActiveSoAIBenchRuns
    from hardware.soaibench.dependencies import SoAIBenchServiceDependencies

__all__ = ("SoAIBenchRegistrationContext",)


@dataclass(frozen=True, slots=True)
class SoAIBenchRegistrationContext:
    deps: SoAIBenchServiceDependencies
    active_runs: ActiveSoAIBenchRuns
    run: JSONDict
    run_id: str
    task_id: str
    device_id: str
    lease_id: str
    user_id: int
    stop_event: asyncio.Event
    start_execution_event: asyncio.Event
    deferred_tool_activity: DeferredToolCallActivity | None
