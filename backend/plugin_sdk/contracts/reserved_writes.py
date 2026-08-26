"""SoAI - Plugin SDK disk-reserved write helpers [backend/plugin_sdk/contracts/reserved_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
from collections.abc import Mapping

from core.errors.exceptions import StateError
from core.filesystem.atomic_writes import atomic_write_text
from core.hardware.reservation_exceptions import (
    DISK_RESERVATION_OPERATION_EXCEPTIONS,
    preserve_primary_exception_cleanup_failure,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict, JSONValue
from plugin_sdk.contracts.disk_claims import claim_plugin_reserved_write
from plugin_sdk.contracts.metadata import _write_metadata_atomic
from plugin_sdk.protocols import (
    ReservedWriteDiskReservationProviderProtocol,
)

__all__ = (
    "write_metadata_with_disk_reservation",
    "write_text_with_disk_reservation",
    "write_text_with_disk_reservation_sync",
)


def _write_text_content(path: str, content: str) -> None:
    def _writer(handle: io.TextIOBase) -> None:
        handle.write(content)

    atomic_write_text(path, _writer, mode="w", encoding="utf-8")


async def write_text_with_disk_reservation(
    storage_manager: ReservedWriteDiskReservationProviderProtocol,
    *,
    path: str,
    content: str,
    operation: str,
    details: Mapping[str, JSONValue] | None = None,
) -> None:
    content_bytes = len(content.encode("utf-8"))
    details_payload: JSONDict = dict(details or {})
    details_payload["required_bytes"] = content_bytes
    reservation = await storage_manager.reserve_disk_space(
        path=path,
        required_bytes=content_bytes,
        operation=operation,
        details=details_payload,
    )
    try:
        async with claim_plugin_reserved_write(
            reservation,
            size_bytes=content_bytes,
            cleanup_action="Reserved text write claim commit after write failure",
        ):
            await asyncio.to_thread(_write_text_content, path, content)
    finally:
        await reservation.release()


def write_text_with_disk_reservation_sync(
    storage_manager: ReservedWriteDiskReservationProviderProtocol,
    *,
    path: str,
    content: str,
    operation: str,
    details: Mapping[str, JSONValue] | None = None,
    loop: asyncio.AbstractEventLoop,
) -> None:
    if not loop.is_running():
        raise StateError("Disk reservation loop is not running.")
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    if current_loop is loop:
        raise StateError("Synchronous disk-reserved writes cannot run on the event loop.")
    content_bytes = len(content.encode("utf-8"))
    details_payload: JSONDict = dict(details or {})
    details_payload["required_bytes"] = content_bytes
    reservation = asyncio.run_coroutine_threadsafe(
        storage_manager.reserve_disk_space(
            path=path,
            required_bytes=content_bytes,
            operation=operation,
            details=details_payload,
        ),
        loop,
    ).result()
    try:
        claim = asyncio.run_coroutine_threadsafe(
            reservation.claim_write_bytes(content_bytes),
            loop,
        ).result()
        try:
            _write_text_content(path, content)
            asyncio.run_coroutine_threadsafe(claim.commit(), loop).result()
        except DISK_RESERVATION_OPERATION_EXCEPTIONS as write_exception:
            try:
                asyncio.run_coroutine_threadsafe(claim.commit(), loop).result()
            except DISK_RESERVATION_OPERATION_EXCEPTIONS as commit_exception:
                preserve_primary_exception_cleanup_failure(
                    write_exception,
                    commit_exception,
                    cleanup_action="Reserved text write claim commit after write failure",
                )
            raise
    finally:
        asyncio.run_coroutine_threadsafe(reservation.release(), loop).result()


async def write_metadata_with_disk_reservation(
    storage_manager: ReservedWriteDiskReservationProviderProtocol,
    *,
    path: str,
    metadata: JSONDict,
    operation: str,
    details: Mapping[str, JSONValue] | None = None,
) -> None:
    metadata_text = serialize_json_compact_stable_strict(metadata)
    metadata_bytes = len(metadata_text.encode("utf-8"))
    details_payload: JSONDict = dict(details or {})
    details_payload["required_bytes"] = metadata_bytes
    reservation = await storage_manager.reserve_disk_space(
        path=path,
        required_bytes=metadata_bytes,
        operation=operation,
        details=details_payload,
    )
    try:
        async with claim_plugin_reserved_write(
            reservation,
            size_bytes=metadata_bytes,
            cleanup_action="Reserved metadata write claim commit after write failure",
        ):
            await asyncio.to_thread(_write_metadata_atomic, path, metadata)
    finally:
        await reservation.release()
