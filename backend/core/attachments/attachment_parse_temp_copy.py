"""SoAI - WebUI attachment parse descriptor temp copy [backend/core/attachments/attachment_parse_temp_copy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.config.byte_sizes import MIB_BYTES
from core.errors.exception_logging import log_handled_exception
from core.files.temp_files import create_secure_temp_file_descriptor
from core.logging.trace import get_logger

__all__ = ("copy_attachment_descriptor_to_temp_path",)

LOGGER_NAME = "SoAI.core.attachments.attachment_parse_temp_copy"
OPERATION_WEBUI_ATTACHMENT_PARSE_CLASSIFY = "webui.attachment_parse.classify"
_DESCRIPTOR_COPY_CHUNK_BYTES = MIB_BYTES


def _log_cleanup_os_error(*, message: str, exception: OSError) -> None:
    log_handled_exception(
        get_logger(LOGGER_NAME),
        exception,
        message=message,
        operation=OPERATION_WEBUI_ATTACHMENT_PARSE_CLASSIFY,
        level="debug",
    )


def _close_descriptor_quietly(*, descriptor: int, message: str) -> None:
    try:
        os.close(descriptor)
    except OSError as exception:
        _log_cleanup_os_error(message=message, exception=exception)


def _remove_path_quietly(*, path: str, message: str) -> None:
    try:
        os.remove(path)
    except OSError as exception:
        _log_cleanup_os_error(message=message, exception=exception)


def _write_chunk(temp_descriptor: int, chunk: bytes) -> None:
    written = 0
    while written < len(chunk):
        written += os.write(temp_descriptor, chunk[written:])


def _copy_with_pread(*, descriptor: int, temp_descriptor: int) -> None:
    read_offset = 0
    while True:
        chunk = os.pread(descriptor, _DESCRIPTOR_COPY_CHUNK_BYTES, read_offset)
        if not chunk:
            return
        _write_chunk(temp_descriptor, chunk)
        read_offset += len(chunk)


def _copy_with_seek_restore(*, descriptor: int, temp_descriptor: int) -> None:
    original_offset = os.lseek(descriptor, 0, os.SEEK_CUR)
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        while True:
            chunk = os.read(descriptor, _DESCRIPTOR_COPY_CHUNK_BYTES)
            if not chunk:
                return
            _write_chunk(temp_descriptor, chunk)
    finally:
        os.lseek(descriptor, original_offset, os.SEEK_SET)


def copy_attachment_descriptor_to_temp_path(*, descriptor: int, filename: str) -> str:
    suffix = os.path.splitext(filename)[1]
    temp_descriptor, temp_path = create_secure_temp_file_descriptor(
        directory=None,
        prefix="soai-provider-",
        suffix=suffix,
    )
    copy_completed = False
    try:
        if os.name == "nt":
            _copy_with_seek_restore(descriptor=descriptor, temp_descriptor=temp_descriptor)
        else:
            _copy_with_pread(descriptor=descriptor, temp_descriptor=temp_descriptor)
        os.fsync(temp_descriptor)
        copy_completed = True
        return temp_path
    finally:
        _close_descriptor_quietly(
            descriptor=temp_descriptor,
            message="Failed to close temporary SoAI provider descriptor.",
        )
        if not copy_completed:
            _remove_path_quietly(
                path=temp_path,
                message="Failed to remove incomplete temporary SoAI provider file.",
            )
