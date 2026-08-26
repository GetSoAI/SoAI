"""SoAI - Hardware subsystem null service composition [backend/app/composition/hardware_null_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.composition.nvidia_nvml_environment import create_nvidia_nvml_environment
from app.lifecycle.coordinator import LifecycleCoordinator
from core.logging.trace import get_logger
from core.system.command_executor import CommandExecutor, CommandExecutorDependencies
from core.terminal.protocols import TerminalServiceProtocol
from hardware.gpu_tuning.null_service import (
    NullHardwareGpuTuningService,
    NullHardwareGpuTuningServiceDependencies,
)
from hardware.manager.null_manager import (
    NullHardwareManager,
    NullHardwareManagerDependencies,
)
from hardware.vendors.nvidia.nvml_preflight import hardware_disabled_nvml_runtime_status
from terminal.null_service import NullTerminalService, NullTerminalServiceDependencies

if TYPE_CHECKING:
    from core.runtime.flags_service import RuntimeFlagsService

__all__ = ("build_null_hardware_services",)

LOGGER_NAME_CORE_SYSTEM_COMMANDS = "SoAI.app.composition.core_system_commands"
LOGGER_NAME_NULLHARDWAREGPUTUNINGSERVICE = "SoAI.app.composition.nullhardwaregputuningservice"
LOGGER_NAME_NULLHARDWAREMANAGER = "SoAI.app.composition.nullhardwaremanager"
LOGGER_NAME_NULLTERMINALSERVICE = "SoAI.app.composition.nullterminalservice"


def build_null_hardware_services(
    *,
    runtime_flags: RuntimeFlagsService,
    lifecycle_coordinator: LifecycleCoordinator,
) -> tuple[
    TerminalServiceProtocol,
    NullHardwareGpuTuningService,
    NullHardwareManager,
    CommandExecutor | None,
]:
    terminal = NullTerminalService(
        NullTerminalServiceDependencies(logger=get_logger(LOGGER_NAME_NULLTERMINALSERVICE)),
    )
    lifecycle_coordinator.register_actor(terminal)
    hardware_gpu_tuning = NullHardwareGpuTuningService(
        NullHardwareGpuTuningServiceDependencies(
            logger=get_logger(LOGGER_NAME_NULLHARDWAREGPUTUNINGSERVICE),
        ),
    )
    lifecycle_coordinator.register_actor(hardware_gpu_tuning)
    nvidia_environment = create_nvidia_nvml_environment(
        nvml_runtime_status=hardware_disabled_nvml_runtime_status(),
    )
    hardware_manager = NullHardwareManager(
        NullHardwareManagerDependencies(
            logger=get_logger(LOGGER_NAME_NULLHARDWAREMANAGER),
            nvidia_nvml_gate=nvidia_environment.nvml_gate,
        ),
    )
    command_executor = None
    if runtime_flags.host_management_available:
        command_executor = CommandExecutor(
            CommandExecutorDependencies(
                executor_logger=get_logger(LOGGER_NAME_CORE_SYSTEM_COMMANDS),
            ),
        )
    return (
        terminal,
        hardware_gpu_tuning,
        hardware_manager,
        command_executor,
    )
