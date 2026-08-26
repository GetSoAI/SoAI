"""SoAI - Periodic minimum hardware spec check task [backend/hardware/manager/min_specs_task.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.system.protocols import CommandExecutorProtocol
from hardware.cpu_rapl import RaplEnergyCache
from hardware.internal_protocols import MinimumSpecsManagerProtocol

__all__ = ("run_periodic_min_specs_check",)

OPERATION = "hardware_manager.periodic_min_specs_check"


async def run_periodic_min_specs_check(
    *,
    manager: MinimumSpecsManagerProtocol,
    executor: CommandExecutorProtocol,
    logger: LoggerProtocol,
    rapl_energy_cache: RaplEnergyCache,
    check_minimum_specs: Callable[
        [MinimumSpecsManagerProtocol, CommandExecutorProtocol, RaplEnergyCache],
        None,
    ],
    interval_seconds: int = 21600,
) -> None:
    while True:
        try:
            await asyncio.to_thread(check_minimum_specs, manager, executor, rapl_energy_cache)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Min specs check failed",
                operation=OPERATION,
            )
        await asyncio.sleep(interval_seconds)
