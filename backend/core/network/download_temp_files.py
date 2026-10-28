"""SoAI - Secure temporary files for network downloads [backend/core/network/download_temp_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
from collections.abc import Callable
from types import TracebackType
from typing import Self

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import ValidationError
from core.files.file_identity import FileIdentity
from core.files.move_with_cancellation import MoveFileCommittedAfterCancellationError
from core.files.temp_files import create_secure_temp_file_descriptor
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.hardware.reservation_exceptions import preserve_primary_exception_cleanup_failure
from core.network.protocols import DownloadInterruptionProtocol

__all__ = ("create_download_temp_handle", "DownloadFile")


def create_download_temp_handle(destination_path: str) -> tuple[io.BufferedWriter, str]:
    destination_dir = os.path.dirname(os.path.abspath(destination_path)) or None
    file_descriptor, temp_path = create_secure_temp_file_descriptor(
        directory=destination_dir,
        prefix=".soai_download_",
        suffix=".part",
    )
    try:
        handle = os.fdopen(file_descriptor, "wb")
    except (OSError, ValueError) as open_exception:
        try:
            os.close(file_descriptor)
        except OSError as close_exception:
            open_exception.add_note(
                f"Download temp file descriptor cleanup failed: {close_exception}",
            )
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError as remove_exception:
                open_exception.add_note(f"Download temp file cleanup failed: {remove_exception}")
        raise
    if not isinstance(handle, io.BufferedWriter):
        handle.close()
        os.remove(temp_path)
        raise ValidationError("Failed to open temporary download file for writing.")
    return handle, temp_path


class DownloadFile:
    def __init__(self, destination_path: str, *, retain_partial: bool = False) -> None:
        self.destination_path = destination_path
        self.retain_partial = retain_partial
        self.handle: io.BufferedWriter | None = None
        self.path = ""
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await run_joined_thread_call(
            self._cleanup,
            exception,
            task_name="download-file-cleanup",
            retain_resources_until_complete=True,
        )

    def _cleanup(self, primary_exception: BaseException | None) -> None:
        close_failure: OSError | None = None
        try:
            self._close()
        except OSError as exception:
            close_failure = exception
        if self.path and not self.retain_partial and not self.committed:
            try:
                os.remove(self.path)
                self.path = ""
            except FileNotFoundError:
                self.path = ""
            except OSError as exception:
                preserve_primary_exception_cleanup_failure(
                    primary_exception or close_failure,
                    exception,
                    cleanup_action="Download file removal",
                )
        if close_failure is not None:
            preserve_primary_exception_cleanup_failure(
                primary_exception, close_failure, cleanup_action="Download file close"
            )

    async def open(
        self,
        opener: Callable[[], tuple[io.BufferedWriter, str]],
    ) -> io.BufferedWriter:
        def create() -> None:
            self.handle, self.path = opener()

        await run_joined_thread_call(
            create,
            task_name="download-file-open",
            retain_resources_until_complete=True,
        )
        if self.handle is None:
            raise ValidationError("Failed to open destination file for writing.")
        return self.handle

    def _close(self) -> None:
        if self.handle is not None:
            self.handle.close()
            self.handle = None

    async def publish(
        self,
        interruption: DownloadInterruptionProtocol,
        *,
        cancellation_id: str = "download",
        verified_identity: FileIdentity | None = None,
    ) -> None:
        await run_joined_thread_call(
            self._close,
            task_name="download-file-close",
            retain_resources_until_complete=True,
        )
        if not self.path:
            raise ValidationError("Failed to finalize downloaded file.")
        interruption.raise_if_cancelled()
        source_path = self.path

        def replace() -> None:
            interruption.raise_if_cancelled()
            if verified_identity is not None:
                with open_regular_binary_no_symlink(source_path) as verified_handle:
                    if (
                        FileIdentity.from_stat(os.fstat(verified_handle.fileno()))
                        != verified_identity
                    ):
                        raise ValidationError("Verified artifact changed before publication.")
            os.replace(source_path, self.destination_path)
            self.committed = True
            self.path = ""

        try:
            await run_joined_thread_call(
                replace,
                task_name="download-file-publish",
                retain_resources_until_complete=True,
            )
            interruption.raise_if_cancelled()
        except (asyncio.CancelledError, TaskCancelledError, ValidationError) as exception:
            if self.committed:
                raise MoveFileCommittedAfterCancellationError(
                    cancellation_id=cancellation_id,
                    source_path=source_path,
                    destination_path=self.destination_path,
                    cancellation_cause=exception,
                ) from exception
            raise
