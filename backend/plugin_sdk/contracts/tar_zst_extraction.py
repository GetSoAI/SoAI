"""SoAI - Safe tar.zst extraction helper for plugins [backend/plugin_sdk/contracts/tar_zst_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
from typing import TYPE_CHECKING

import zstandard

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.config.byte_sizes import MIB_BYTES
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.temp_files import create_secure_temp_file_descriptor
from core.filesystem.open_files import open_binary
from core.hardware.reservation_exceptions import (
    DISK_RESERVATION_OPERATION_EXCEPTIONS,
    preserve_primary_exception_cleanup_failure,
)
from core.logging.trace import get_logger
from plugin_sdk.contracts.archive_extraction import (
    async_safe_tar_extractall,
    check_archive_shutdown,
)
from plugin_sdk.contracts.disk_claims import claim_plugin_reserved_write

if TYPE_CHECKING:
    from core.plugins.protocols_runtime import (
        PluginStorageReservationLeaseProtocol,
        PluginStorageRuntimeProtocol,
    )

__all__ = ("async_safe_tar_zst_extractall",)

LOGGER_NAME = "SoAI.plugin_sdk.contracts.tar_zst_extraction"
OPERATION = "plugin_sdk.tar_zst_extraction.cleanup_temp"


async def async_safe_tar_zst_extractall(
    archive_path: str,
    dest_dir: str,
    *,
    reservation_provider: PluginStorageRuntimeProtocol,
    temp_dir: str | None = None,
    max_decompressed_bytes: int | None = None,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not archive_path.strip():
        raise ValidationError("archive_path must be provided.")
    if not dest_dir.strip():
        raise ValidationError("dest_dir must be provided.")
    if not os.path.exists(archive_path):
        raise ValidationError(f"Archive not found: {archive_path}")
    resolved_temp_dir = temp_dir if isinstance(temp_dir, str) and temp_dir.strip() else None
    if resolved_temp_dir is not None:
        os.makedirs(resolved_temp_dir, exist_ok=True)
    fd, temp_tar_path = create_secure_temp_file_descriptor(
        directory=resolved_temp_dir,
        prefix="soai_tar_zst_",
        suffix=".tar",
    )
    os.close(fd)

    held_reservations: list[PluginStorageReservationLeaseProtocol] = []
    event = shutdown_event if shutdown_event is not None else asyncio.Event()
    primary_exception: BaseException | None = None
    try:
        await _decompress_to_temp_tar(
            archive_path=archive_path,
            temp_tar_path=temp_tar_path,
            max_decompressed_bytes=max_decompressed_bytes,
            reservation_provider=reservation_provider,
            held_reservations=held_reservations,
            shutdown_event=event,
        )
        await async_safe_tar_extractall(
            temp_tar_path,
            dest_dir,
            reservation_provider=reservation_provider,
            shutdown_event=event,
        )
    except asyncio.CancelledError as exception:
        primary_exception = exception
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        primary_exception = exception
        raise
    finally:
        try:
            await asyncio.to_thread(os.remove, temp_tar_path)
        except OSError as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to remove temporary tar file after extraction (non-critical).",
                operation=OPERATION,
                details={"temp_tar_path": temp_tar_path},
                level="debug",
            )
        finally:
            try:
                await _release_reservations(tuple(held_reservations))
            except DISK_RESERVATION_OPERATION_EXCEPTIONS as release_exception:
                preserve_primary_exception_cleanup_failure(
                    primary_exception,
                    release_exception,
                    cleanup_action="Plugin tar.zst reservation release",
                )


async def _decompress_to_temp_tar(
    *,
    archive_path: str,
    temp_tar_path: str,
    max_decompressed_bytes: int | None,
    reservation_provider: PluginStorageRuntimeProtocol,
    held_reservations: list[PluginStorageReservationLeaseProtocol],
    shutdown_event: asyncio.Event,
) -> None:
    declared_reservation: PluginStorageReservationLeaseProtocol | None = None
    if max_decompressed_bytes is not None:
        declared_reservation = await reservation_provider.reserve_disk_space(
            path=temp_tar_path,
            required_bytes=max_decompressed_bytes,
            operation="plugin_sdk.tar_zst_extraction.decompress",
            details={"archive_path": archive_path, "temp_tar_path": temp_tar_path},
        )
        held_reservations.append(declared_reservation)
    try:
        decompressor = zstandard.ZstdDecompressor()
        decompressed_bytes = 0
        with open_binary(archive_path, mode="rb") as source_handle:
            with decompressor.stream_reader(source_handle) as reader:
                with open_binary(temp_tar_path, mode="wb") as dest_handle:
                    while True:
                        check_archive_shutdown(shutdown_event)
                        chunk = await run_joined_thread_call(
                            reader.read,
                            MIB_BYTES,
                            task_name="plugin-zstd-read",
                            retain_resources_until_complete=True,
                            on_cancel=shutdown_event.set,
                        )
                        if not chunk:
                            break
                        decompressed_bytes += len(chunk)
                        if (
                            max_decompressed_bytes is not None
                            and decompressed_bytes > max_decompressed_bytes
                        ):
                            raise ValidationError(
                                "Decompressed tar.zst archive exceeds the configured limit.",
                            )
                        await _write_decompressed_chunk(
                            temp_tar_path=temp_tar_path,
                            archive_path=archive_path,
                            chunk=chunk,
                            declared_reservation=declared_reservation,
                            reservation_provider=reservation_provider,
                            held_reservations=held_reservations,
                            dest_handle=dest_handle,
                        )
    except zstandard.ZstdError as exception:
        raise ValidationError(
            f"Invalid or incomplete Zstandard archive: {archive_path}",
            operation="plugin_sdk.tar_zst_extraction.decompress",
            cause=exception,
        ) from exception


async def _write_decompressed_chunk(
    *,
    temp_tar_path: str,
    archive_path: str,
    chunk: bytes,
    declared_reservation: PluginStorageReservationLeaseProtocol | None,
    reservation_provider: PluginStorageRuntimeProtocol,
    held_reservations: list[PluginStorageReservationLeaseProtocol],
    dest_handle: io.BufferedWriter,
) -> None:
    if declared_reservation is not None:
        async with claim_plugin_reserved_write(
            declared_reservation,
            size_bytes=len(chunk),
            cleanup_action="Plugin SDK tar.zst declared claim commit after write failure",
        ):
            await run_joined_thread_call(
                dest_handle.write,
                chunk,
                task_name="plugin-zstd-write",
                retain_resources_until_complete=True,
            )
        return
    chunk_reservation = await reservation_provider.reserve_disk_space(
        path=temp_tar_path,
        required_bytes=len(chunk),
        operation="plugin_sdk.tar_zst_extraction.decompress",
        details={"archive_path": archive_path, "temp_tar_path": temp_tar_path},
    )
    held_reservations.append(chunk_reservation)
    async with claim_plugin_reserved_write(
        chunk_reservation,
        size_bytes=len(chunk),
        cleanup_action="Plugin SDK tar.zst chunk claim commit after write failure",
    ):
        await run_joined_thread_call(
            _write_and_flush,
            dest_handle,
            chunk,
            task_name="plugin-zstd-write",
            retain_resources_until_complete=True,
        )
    await chunk_reservation.release()
    held_reservations.remove(chunk_reservation)


def _write_and_flush(dest_handle: io.BufferedWriter, chunk: bytes) -> None:
    dest_handle.write(chunk)
    dest_handle.flush()


async def _release_reservations(
    reservations: tuple[PluginStorageReservationLeaseProtocol, ...],
) -> None:
    first_exception: Exception | None = None
    for reservation in reversed(reservations):
        try:
            await reservation.release()
        except DISK_RESERVATION_OPERATION_EXCEPTIONS as exception:
            if first_exception is None:
                first_exception = exception
            else:
                preserve_primary_exception_cleanup_failure(
                    first_exception,
                    exception,
                    cleanup_action="Plugin tar.zst reservation release",
                )
    if first_exception is not None:
        raise first_exception
