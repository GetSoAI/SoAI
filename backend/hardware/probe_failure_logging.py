"""SoAI - Hardware probe failure logging [backend/hardware/probe_failure_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.system.protocols import (
        CommandExecutorProtocol,
        CommandResultProtocol,
    )

__all__ = ("execute_hardware_probe_command",)


def execute_hardware_probe_command(
    executor: CommandExecutorProtocol,
    command: str | Sequence[str],
    *,
    logger: LoggerProtocol,
    message: str,
    operation: str,
    timeout: int,
) -> CommandResultProtocol | None:
    try:
        return executor.execute(command, timeout=timeout, shell=False, use_sudo=False)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Hardware probe command failed (non-critical).",
            operation=operation,
            details={"probe_message": message},
            level="trace",
        )
        return None
