"""SoAI - Managed upload artifact cleanup [backend/core/files/upload_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging

from core.files.operations import async_remove_if_exists
from core.logging.trace import get_logger

__all__ = ("cleanup_upload_artifacts",)

LOGGER_NAME = "SoAI.core.files.upload_cleanup"


async def cleanup_upload_artifacts(
    *,
    temp_path: str | None,
    permanent_path: str | None,
    log_level: int = logging.WARNING,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if permanent_path:
        await async_remove_if_exists(permanent_path, logger=logger, log_level=log_level)
    if temp_path:
        await async_remove_if_exists(temp_path, logger=logger, log_level=log_level)
