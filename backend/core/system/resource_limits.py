"""SoAI - Process resource limit configuration [backend/core/system/resource_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
import sys

from core.logging.configuration_constants import DEFAULT_LOG_DATE_FORMAT
from core.logging.formatters import UnifiedFormatter
from core.logging.trace import get_logger
from core.platform.os import is_windows

__all__ = ("configure_resource_limits",)

LOGGER_NAME = "SoAI.core.system.resource_limits"
ROOT_FILE_DESCRIPTOR_LIMIT = 1_048_576

if sys.platform != "win32":
    import resource

    RESOURCE = resource
else:
    RESOURCE = None


def configure_resource_limits() -> None:
    logger = get_logger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            UnifiedFormatter(
                "%(asctime)s - [SoAI/Bootstrap] - %(levelname)s - %(message)s",
                DEFAULT_LOG_DATE_FORMAT,
            ),
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    if is_windows():
        logger.debug("Adjusting the maximum number of open files is not supported on Windows.")
        return
    if RESOURCE is None:
        logger.debug("Adjusting the maximum number of open files is unavailable on this platform.")
        return
    soft, hard = RESOURCE.getrlimit(RESOURCE.RLIMIT_NOFILE)
    logger.debug("Current file descriptor limits: soft=%s, hard=%s (Unix).", soft, hard)
    if os.geteuid() == 0:
        try:
            RESOURCE.setrlimit(
                RESOURCE.RLIMIT_NOFILE,
                (ROOT_FILE_DESCRIPTOR_LIMIT, ROOT_FILE_DESCRIPTOR_LIMIT),
            )
            new_soft, new_hard = RESOURCE.getrlimit(RESOURCE.RLIMIT_NOFILE)
            logger.debug(
                "Running as root. Set file descriptor limits to: soft=%s, hard=%s.",
                new_soft,
                new_hard,
            )
        except (ValueError, PermissionError) as exception:
            logger.warning("Failed to raise file descriptor limits. Reason: %s", str(exception))
    else:
        logger.debug("Not running as root. Will not attempt to raise file descriptor limits.")
