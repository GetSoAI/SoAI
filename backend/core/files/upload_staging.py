"""SoAI - Upload staging helpers [backend/core/files/upload_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from core.files.operations import async_remove

__all__ = (
    "cleanup_temp_file",
    "cleanup_temp_files",
)


async def cleanup_temp_file(path: str | None) -> None:
    if not path:
        return
    try:
        await async_remove(path)
    except FileNotFoundError:
        return


async def cleanup_temp_files(paths: Iterable[str | None]) -> None:
    first_failure: Exception | asyncio.CancelledError | None = None
    for path in paths:
        try:
            await cleanup_temp_file(path)
        except (OSError, asyncio.CancelledError) as exception:
            if first_failure is None:
                first_failure = exception
            else:
                first_failure.add_note(f"Additional cleanup failure: {exception}")
    if first_failure is not None:
        raise first_failure
