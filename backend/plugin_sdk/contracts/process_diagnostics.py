"""SoAI - Bounded managed process log diagnostics [backend/plugin_sdk/contracts/process_diagnostics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Sequence

from core.timing.constants import STANDARD_DELAY_SEC

__all__ = ("read_recent_process_log",)


def _read_recent_process_log(file_path: str, max_bytes: int) -> str:
    file_descriptor = os.open(file_path, os.O_RDONLY)
    try:
        end_offset = os.lseek(file_descriptor, 0, os.SEEK_END)
        os.lseek(file_descriptor, max(0, end_offset - max_bytes), os.SEEK_SET)
        return os.read(file_descriptor, max_bytes).decode("utf-8", errors="replace")
    finally:
        os.close(file_descriptor)


async def read_recent_process_log(
    file_path: str | None,
    *,
    logger: logging.Logger,
    log_consumer_tasks: Sequence[asyncio.Task[None]] = (),
    max_bytes: int = 65536,
) -> str:
    if not file_path or max_bytes <= 0:
        return ""
    pending_consumers = {task for task in log_consumer_tasks if not task.done()}
    if pending_consumers:
        await asyncio.wait(pending_consumers, timeout=STANDARD_DELAY_SEC)
    try:
        return await asyncio.to_thread(_read_recent_process_log, file_path, max_bytes)
    except OSError as exception:
        logger.warning(
            "Failed to read managed process diagnostics from %s: %s",
            file_path,
            f"{type(exception).__name__}: {exception}",
        )
        return ""
