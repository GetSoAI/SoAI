"""SoAI - Wallpaper metadata extraction [backend/webui/manager/wallpaper_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import mimetypes
import os
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from webui.manager.image_size import extract_image_size_sync

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict

__all__ = (
    "collect_wallpaper_metadata",
    "read_image_size",
)

OPERATION = "webui.wallpaper.read_image_size"


async def read_image_size(
    *,
    file_path: str,
    mime_type: str | None,
    logger: TraceLogger,
) -> tuple[int, int] | None:
    try:
        manual = await asyncio.to_thread(extract_image_size_sync, file_path, mime_type)
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        log_exception(
            logger,
            error,
            message="Failed to read wallpaper dimensions",
            operation=OPERATION,
            details={"file_path": file_path, "mime_type": mime_type},
            level="warning",
        )
        manual = None
    if manual:
        return manual
    return None


async def collect_wallpaper_metadata(
    *,
    file_path: str,
    stat_result: os.stat_result,
    logger: TraceLogger,
) -> JSONDict:
    metadata: JSONDict = {"size_bytes": stat_result.st_size}
    mime, _ = mimetypes.guess_type(file_path)
    if mime:
        metadata["type"] = mime
    size = await read_image_size(file_path=file_path, mime_type=mime, logger=logger)
    if size:
        width, height = size
        metadata["width"] = width
        metadata["height"] = height
    return metadata
