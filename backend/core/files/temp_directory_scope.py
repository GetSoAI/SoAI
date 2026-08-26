"""SoAI - Cancellation-safe temporary directory scope [backend/core/files/temp_directory_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import shutil
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.temp_files import create_secure_temp_directory

__all__ = (
    "create_scoped_temp_directory",
    "remove_scoped_temp_directory",
    "scoped_temp_directory",
)


def create_scoped_temp_directory(directory: str | None, prefix: str) -> str:
    return create_secure_temp_directory(directory=directory, prefix=prefix)


def remove_scoped_temp_directory(path: str) -> bool:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return False
    return True


@asynccontextmanager
async def scoped_temp_directory(
    *,
    directory: str | None,
    prefix: str,
    operation_label: str,
) -> AsyncGenerator[str]:
    temp_dir = await run_joined_thread_call(
        create_scoped_temp_directory,
        directory,
        prefix,
        task_name=f"{operation_label}-scratch-create",
        cancelled_result_cleanup=remove_scoped_temp_directory,
    )
    primary_exception: BaseException | None = None
    try:
        yield temp_dir
    except asyncio.CancelledError as exception:
        primary_exception = exception
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        primary_exception = exception
        raise
    finally:
        try:
            await uncancel_then_cleanup(
                run_joined_thread_call(
                    remove_scoped_temp_directory,
                    temp_dir,
                    task_name=f"{operation_label}-scratch-remove",
                ),
            )
        except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
            if primary_exception is None:
                raise
            primary_exception.add_note(f"Temporary directory cleanup failed: {cleanup_exception}")
