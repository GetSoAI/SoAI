"""SoAI - SoAIBench worker execution context [backend/hardware/soaibench/worker_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.hardware.protocols import HardwareManagerProtocol
    from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict
    from hardware.soaibench.telemetry import SoAIBenchTelemetryDiagnostics
    from hardware.soaibench.types import SoAIBenchGpuIdentity

__all__ = (
    "SoAIBenchWorkerEventContext",
    "SoAIBenchWorkerRuntimeContext",
    "SoAIBenchWorkerState",
)


@dataclass(frozen=True, slots=True)
class SoAIBenchWorkerEventContext:
    event_bus: EventBusProtocol
    logger: LoggerProtocol
    task_id: str


@dataclass(slots=True)
class SoAIBenchWorkerState:
    current_run: JSONDict
    terminal_run: JSONDict | None = None


@dataclass(frozen=True, slots=True)
class SoAIBenchWorkerRuntimeContext:
    database_hardware: DatabaseSoAIBenchProtocol
    hardware_manager: HardwareManagerProtocol
    logger: LoggerProtocol
    task_registry: TaskRegistryProtocol
    run_id: str
    task_id: str
    identity: SoAIBenchGpuIdentity
    started_at_ms: int
    base_summary: JSONDict
    settings_snapshot: JSONDict
    temperature_limit_celsius: float | None
    stop_event: asyncio.Event
    telemetry_diagnostics: SoAIBenchTelemetryDiagnostics
    state: SoAIBenchWorkerState
