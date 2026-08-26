"""SoAI - Minimum system spec checks [backend/hardware/monitoring/minimum_specs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from hardware.cpu_rapl import RaplEnergyCache
from hardware.info_cpu import get_cpu_info
from hardware.info_memory import get_memory_info
from hardware.internal_protocols import MinimumSpecsManagerProtocol
from hardware.storage.path_resolution import collect_disk_free_bytes

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol

__all__ = ("check_minimum_specs",)

OPERATION_HARDWARE_MINIMUM_SPECS_CPU = "hardware.minimum_specs.cpu"
OPERATION_HARDWARE_MINIMUM_SPECS_DISK = "hardware.minimum_specs.disk"
OPERATION_HARDWARE_MINIMUM_SPECS_RAM = "hardware.minimum_specs.ram"


def check_minimum_specs(
    manager: MinimumSpecsManagerProtocol,
    executor: CommandExecutorProtocol,
    rapl_energy_cache: RaplEnergyCache,
) -> None:
    if not manager.min_specs_enabled:
        return
    violations: list[str] = []
    try:
        cpu_info = get_cpu_info(executor, rapl_energy_cache=rapl_energy_cache)
        if cpu_info:
            cores_value = cpu_info[0].get("physical_cores")
            physical_cores = int(cores_value) if isinstance(cores_value, int | float) else 0
            if physical_cores < 2:
                violations.append(f"CPU cores ({physical_cores} < 2)")
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            manager.logger,
            exception,
            message="CPU minimum spec check skipped (non-critical).",
            operation=OPERATION_HARDWARE_MINIMUM_SPECS_CPU,
            level="trace",
        )
    try:
        memory_info = get_memory_info()
        total_value = memory_info.get("total_gb")
        total_gb = float(total_value) if isinstance(total_value, int | float) else 0.0
        if total_gb < 2.0:
            violations.append(f"RAM ({total_gb:.1f} GB < 2.0 GB)")
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            manager.logger,
            exception,
            message="RAM minimum spec check skipped (non-critical).",
            operation=OPERATION_HARDWARE_MINIMUM_SPECS_RAM,
            level="trace",
        )
    try:
        free_bytes = collect_disk_free_bytes(manager.base_dir)
        free_gb = (float(free_bytes) / 1024**3) if free_bytes is not None else 0.0
        if free_gb < 1.0:
            violations.append(f"Free disk space ({free_gb:.1f} GB < 1.0 GB)")
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            manager.logger,
            exception,
            message="Disk minimum spec check skipped (non-critical).",
            operation=OPERATION_HARDWARE_MINIMUM_SPECS_DISK,
            level="trace",
        )
    if violations:
        manager.logger.warning("System below minimum specs: %s", ", ".join(violations))
