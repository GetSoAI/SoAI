"""SoAI - Windows CLI lifecycle request writing [backend/app/cli/windows_lifecycle_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import Literal

import psutil

from app.cli.restart_request import write_lifecycle_request
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS

__all__ = ("write_windows_lifecycle_request",)

OPERATION_WINDOWS_LIFECYCLE_REQUEST_WRITE = "app.cli.windows_lifecycle_request.write"


def write_windows_lifecycle_request(
    base_dir: str,
    pid: int,
    action: Literal["restart", "stop"],
    logger: logging.Logger,
) -> str | None:
    try:
        return write_lifecycle_request(base_dir, pid, action, logger)
    except psutil.NoSuchProcess:
        logger.info(
            "SoAI process %s exited before %s request could be written.",
            pid,
            action,
        )
        return None
    except psutil.Error as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to write {action} request due to psutil error.",
            operation=OPERATION_WINDOWS_LIFECYCLE_REQUEST_WRITE,
            details={"action": action, "pid": pid},
            level="error",
        )
        return None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to write {action} request.",
            operation=OPERATION_WINDOWS_LIFECYCLE_REQUEST_WRITE,
            details={"action": action, "pid": pid},
            level="error",
        )
        return None
