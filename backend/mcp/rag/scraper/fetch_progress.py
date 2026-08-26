"""SoAI - Progress callback handling for web scraping [backend/mcp/rag/scraper/fetch_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from mcp.rag.scraper.internal_protocols import ProgressCallbackProtocol

__all__ = ("invoke_progress_callback",)

LOGGER_NAME = "SoAI.mcp.rag.fetch_progress"
OPERATION = "mcp.rag.scraper.invoke_progress_callback"


async def invoke_progress_callback(
    callback: ProgressCallbackProtocol | None,
    current: int,
    total: int | None,
    url: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not callback:
        return
    try:
        if inspect.iscoroutinefunction(callback):
            await callback(current, total, url)
        else:
            result = callback(current, total, url)
            if asyncio.iscoroutine(result):
                await result
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Progress callback failed (non-critical).",
            operation=OPERATION,
            details={"url": url},
            level="debug",
        )
