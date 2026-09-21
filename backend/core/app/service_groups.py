"""SoAI - Shared application service groups [backend/core/app/service_groups.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.hardware.protocols import (
    HardwareControlServiceProtocol,
    HardwareGpuTuningProtocol,
    HardwareManagerProtocol,
)
from core.hardware.protocols_soaibench import SoAIBenchServiceProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.terminal.protocols import TerminalServiceProtocol

__all__ = ("HardwareRuntimeServices",)


@dataclass(slots=True, frozen=True)
class HardwareRuntimeServices:
    manager: HardwareManagerProtocol
    gpu_tuning: HardwareGpuTuningProtocol
    control: HardwareControlServiceProtocol
    soaibench: SoAIBenchServiceProtocol
    terminal: TerminalServiceProtocol
    storage: StorageManagerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="HardwareRuntimeServices",
            manager=self.manager,
            gpu_tuning=self.gpu_tuning,
            control=self.control,
            soaibench=self.soaibench,
            terminal=self.terminal,
            storage=self.storage,
        )
