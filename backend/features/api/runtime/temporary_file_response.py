"""SoAI - Guaranteed-cleanup temporary file response [backend/features/api/runtime/temporary_file_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import errno
import os
import stat
import sys
from typing import override

from starlette.responses import FileResponse
from starlette.types import Receive, Scope, Send

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.files.file_identity import FileIdentity
from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.secure_open_flags import secure_read_only_open_flags
from core.files.windows_handle_operations import mark_windows_file_descriptor_for_deletion
from core.files.windows_managed_path_handles import open_windows_managed_path_handles
from core.logging.trace import get_logger
from features.api.runtime.file_descriptor_response import FileDescriptorResponse

__all__ = ("TemporaryFileResponse",)

LOGGER_NAME = "SoAI.features.api.temporary_file_response"
OPERATION_TEMPORARY_FILE_RESPONSE_CLEANUP = "features.api.temporary_file_response.cleanup"
OPERATION_TEMPORARY_FILE_RESPONSE_CLOSE = "features.api.temporary_file_response.close"
OPERATION_TEMPORARY_FILE_RESPONSE_OPEN = "features.api.temporary_file_response.open"
OPERATION_TEMPORARY_FILE_RESPONSE_UNLINK = "features.api.temporary_file_response.unlink"


class TemporaryFileResponse(FileResponse):
    def __init__(
        self,
        path: str,
        *,
        expected_identity: FileIdentity,
        filename: str | None = None,
        media_type: str | None = None,
    ) -> None:
        super().__init__(path, filename=filename, media_type=media_type)
        self._expected_identity = expected_identity

    @override
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        original_path = _require_temporary_response_path(self.path)
        anchor_descriptor = -1
        temporary_path_owned = False
        temporary_path_removed = False
        try:
            anchor_descriptor, opened_status, temporary_path_removed = await asyncio.to_thread(
                _open_stable_temporary_file,
                os.fspath(original_path),
                self._expected_identity,
            )
            temporary_path_owned = True
            if os.name != "nt":
                await uncancel_and_wait(
                    asyncio.to_thread(
                        _unlink_open_posix_temporary_file,
                        os.fspath(original_path),
                    ),
                )
                temporary_path_removed = True
            descriptor_response = FileDescriptorResponse(
                original_path,
                descriptor=anchor_descriptor,
                stat_result=opened_status,
                status_code=self.status_code,
                headers=dict(self.headers),
                media_type=self.media_type,
            )
            await descriptor_response(scope, receive, send)
        finally:
            primary_exception = sys.exception()
            close_exception = _close_descriptors(
                (anchor_descriptor,),
                primary_exception=primary_exception,
            )
            if temporary_path_owned and not temporary_path_removed:
                await self._remove_temporary_file(
                    original_path,
                    primary_exception or close_exception,
                )
            if primary_exception is None and close_exception is not None:
                raise StateError(
                    "Failed to close temporary response file.",
                    operation=OPERATION_TEMPORARY_FILE_RESPONSE_CLOSE,
                    cause=close_exception,
                ) from close_exception

    async def _remove_temporary_file(
        self,
        path: str,
        primary_exception: BaseException | None,
    ) -> None:
        try:
            await uncancel_and_wait(asyncio.to_thread(os.remove, path))
        except FileNotFoundError:
            return
        except OSError as cleanup_exception:
            if primary_exception is not None:
                primary_exception.add_note(
                    f"Temporary response file cleanup failed: {cleanup_exception}",
                )
                log_exception(
                    get_logger(LOGGER_NAME),
                    cleanup_exception,
                    message="Failed to clean up temporary response file",
                    operation=OPERATION_TEMPORARY_FILE_RESPONSE_CLEANUP,
                    details={"path": path},
                )
                return
            raise StateError(
                "Failed to clean up temporary response file.",
                operation=OPERATION_TEMPORARY_FILE_RESPONSE_CLEANUP,
                cause=cleanup_exception,
            ) from cleanup_exception


def _require_temporary_response_path(value: str | os.PathLike[str]) -> str:
    return os.fspath(value)


def _open_stable_temporary_file(
    path: str,
    expected_identity: FileIdentity,
) -> tuple[int, os.stat_result, bool]:
    if os.name == "nt":
        try:
            with open_windows_managed_path_handles(
                os.path.dirname(path),
                path,
                require_directory=False,
                read_leaf=True,
                allow_leaf_delete=True,
            ) as opened_path:
                _require_matching_identity(
                    expected_identity,
                    FileIdentity.from_stat(opened_path.stat_result),
                )
                descriptor = opened_path.detach_leaf_file_descriptor()
                try:
                    mark_windows_file_descriptor_for_deletion(descriptor)
                except FileStorageSecurityError as exception:
                    _close_descriptors((descriptor,), primary_exception=exception)
                    raise
                return descriptor, opened_path.stat_result, True
        except FileStorageSecurityError as exception:
            raise StateError(
                "Temporary response file could not be opened securely.",
                operation=OPERATION_TEMPORARY_FILE_RESPONSE_OPEN,
                cause=exception,
            ) from exception
    try:
        descriptor = os.open(path, secure_read_only_open_flags(directory=False))
    except (FileStorageSecurityError, OSError) as exception:
        raise StateError(
            "Temporary response file could not be opened securely.",
            operation=OPERATION_TEMPORARY_FILE_RESPONSE_OPEN,
            cause=exception,
        ) from exception
    completed = False
    try:
        try:
            opened_status = os.fstat(descriptor)
        except OSError as exception:
            raise StateError(
                "Temporary response file could not be inspected.",
                operation=OPERATION_TEMPORARY_FILE_RESPONSE_OPEN,
                cause=exception,
            ) from exception
        if not stat.S_ISREG(opened_status.st_mode):
            raise StateError(
                "Temporary response path is not a regular file.",
                operation=OPERATION_TEMPORARY_FILE_RESPONSE_OPEN,
            )
        _require_matching_identity(
            expected_identity,
            FileIdentity.from_stat(opened_status),
        )
        completed = True
        return descriptor, opened_status, False
    finally:
        if not completed:
            primary_exception = sys.exception()
            close_exception = _close_descriptors(
                (descriptor,),
                primary_exception=primary_exception,
            )
            if primary_exception is None and close_exception is not None:
                raise StateError(
                    "Failed to close temporary response descriptor.",
                    operation=OPERATION_TEMPORARY_FILE_RESPONSE_CLOSE,
                    cause=close_exception,
                ) from close_exception


def _unlink_open_posix_temporary_file(path: str) -> None:
    try:
        os.remove(path)
    except OSError as exception:
        raise StateError(
            "Temporary response file could not be unlinked before delivery.",
            operation=OPERATION_TEMPORARY_FILE_RESPONSE_UNLINK,
            cause=exception,
        ) from exception


def _require_matching_identity(expected: FileIdentity, actual: FileIdentity) -> None:
    if expected == actual and actual.is_regular_file:
        return
    raise StateError(
        "Temporary response file changed before delivery.",
        operation=OPERATION_TEMPORARY_FILE_RESPONSE_OPEN,
    )


def _close_descriptors(
    descriptors: tuple[int, ...],
    *,
    primary_exception: BaseException | None,
) -> OSError | None:
    first_close_exception: OSError | None = None
    for descriptor in descriptors:
        if descriptor < 0:
            continue
        try:
            os.close(descriptor)
        except OSError as close_exception:
            if close_exception.errno == errno.EBADF:
                continue
            if first_close_exception is None:
                first_close_exception = close_exception
    if first_close_exception is not None and primary_exception is not None:
        primary_exception.add_note(
            f"Temporary response descriptor cleanup failed: {first_close_exception}",
        )
    return first_close_exception
