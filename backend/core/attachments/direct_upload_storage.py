"""SoAI - Direct attachment byte storage [backend/core/attachments/direct_upload_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from typing import TYPE_CHECKING

from core.attachments.direct_upload_metadata import (
    normalize_direct_upload_suffix,
)
from core.attachments.direct_upload_persistence import (
    StoredDirectAttachmentUpload,
    build_stored_direct_attachment_upload,
    move_direct_attachment_to_storage,
)
from core.config.byte_sizes import MIB_BYTES
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.operations import secure_filename
from core.files.temp_files import create_secure_temp_file_descriptor
from core.files.upload_cleanup import cleanup_upload_artifacts
from core.filesystem.file_sync import flush_and_fsync_file
from core.filesystem.open_files import open_binary
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.timing.constants import CONTROL_TIMEOUT_SEC

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )
    from core.tasks.protocols import (
        CancellationEventBusProtocol,
        CancellationHistoryProtocol,
        TokenCollectionProtocol,
    )

__all__ = (
    "store_direct_attachment_upload",
    "store_staged_direct_attachment_upload",
)

_UPLOAD_CHUNK_BYTES = MIB_BYTES
LOGGER_NAME = "SoAI.core.attachments.direct_upload_storage"
OPERATION_DIRECT_ATTACHMENT_UPLOAD_FAILURE = "chat.direct_attachment_upload.failure"


async def _stream_bytes_to_temp_path(
    *,
    read_chunk: Callable[[int], Awaitable[bytes]],
    max_bytes: int,
    temp_path: str,
    storage_manager: StorageManagerProtocol,
    declared_reservation: DiskSpaceReservationLeaseProtocol | None,
) -> tuple[int, str]:
    total = 0
    digest = hashlib.sha256()
    with open_binary(temp_path, mode="wb") as handle:
        while True:
            try:
                chunk = await asyncio.wait_for(
                    read_chunk(_UPLOAD_CHUNK_BYTES),
                    timeout=float(CONTROL_TIMEOUT_SEC),
                )
            except TimeoutError as exception:
                raise ValidationError("Attachment upload stream read timed out.") from exception
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValidationError(
                    f"Uploaded file exceeds the configured limit of {max_bytes} bytes.",
                )
            digest.update(chunk)
            chunk_length = len(chunk)
            if declared_reservation is not None:
                with claim_reserved_write(declared_reservation, size_bytes=chunk_length):
                    handle.write(chunk)
                    flush_and_fsync_file(handle)
                continue
            with storage_manager.reserve_disk_space(
                path=temp_path,
                required_bytes=chunk_length,
                operation="chat.direct_attachment_upload.temp",
                details={
                    "purpose": "chat_direct_attachment_temp_chunk",
                    "temp_path": temp_path,
                    "chunk_bytes": chunk_length,
                },
            ) as reservation:
                with claim_reserved_write(reservation, size_bytes=chunk_length):
                    handle.write(chunk)
                    flush_and_fsync_file(handle)
    if total <= 0:
        raise ValidationError("Uploaded file is empty.")
    return (total, digest.hexdigest().lower())


def _validate_declared_size(declared_size: int | None, *, max_bytes: int) -> int | None:
    if declared_size is None or declared_size <= 0:
        return None
    if declared_size > max_bytes:
        raise ValidationError(f"Uploaded file exceeds the configured limit of {max_bytes} bytes.")
    return declared_size


async def store_direct_attachment_upload(
    *,
    read_chunk: Callable[[int], Awaitable[bytes]],
    declared_size: int | None,
    declared_content_type: str | None,
    display_name: str,
    storage_root: str,
    max_bytes: int,
    storage_manager: StorageManagerProtocol,
    token_collection: TokenCollectionProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    cancellation_id: str,
) -> StoredDirectAttachmentUpload:
    safe_filename = secure_filename(display_name)
    if not safe_filename:
        raise ValidationError("display_name is invalid.")
    file_id = f"file-{uuid.uuid4().hex}"
    permanent_filename = f"{file_id}_{safe_filename}"
    permanent_path = os.path.join(storage_root, permanent_filename)
    file_descriptor, temp_path = create_secure_temp_file_descriptor(
        directory=None,
        prefix=".soai-chat-attachment-",
        suffix=normalize_direct_upload_suffix(safe_filename),
    )
    os.close(file_descriptor)
    declared_reservation: DiskSpaceReservationLeaseProtocol | None = None
    try:
        validated_size = _validate_declared_size(declared_size, max_bytes=max_bytes)
        if validated_size is not None:
            declared_reservation = storage_manager.reserve_disk_space(
                path=temp_path,
                required_bytes=validated_size,
                operation="chat.direct_attachment_upload.temp_declared",
                details={
                    "purpose": "chat_direct_attachment_temp_stream",
                    "temp_path": temp_path,
                    "declared_size_bytes": validated_size,
                },
            )
        size_bytes, content_sha256 = await _stream_bytes_to_temp_path(
            read_chunk=read_chunk,
            max_bytes=max_bytes,
            temp_path=temp_path,
            storage_manager=storage_manager,
            declared_reservation=declared_reservation,
        )
        await move_direct_attachment_to_storage(
            temp_path=temp_path,
            permanent_path=permanent_path,
            size_bytes=size_bytes,
            storage_manager=storage_manager,
            token_collection=token_collection,
            cancellation_history=cancellation_history,
            cancellation_event_bus=cancellation_event_bus,
            cancellation_id=cancellation_id,
        )
    except asyncio.CancelledError:
        await cleanup_upload_artifacts(temp_path=temp_path, permanent_path=permanent_path)
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_DIRECT_ATTACHMENT_UPLOAD_FAILURE,
        )
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Attachment upload failed before staging.",
            operation=OPERATION_DIRECT_ATTACHMENT_UPLOAD_FAILURE,
            details={"temp_path": temp_path, "permanent_path": permanent_path},
        )
        await cleanup_upload_artifacts(temp_path=temp_path, permanent_path=permanent_path)
        raise coerced from exception
    finally:
        if declared_reservation is not None:
            declared_reservation.release()
    return build_stored_direct_attachment_upload(
        file_id=file_id,
        permanent_path=permanent_path,
        safe_filename=safe_filename,
        declared_content_type=declared_content_type,
        size_bytes=size_bytes,
        content_sha256=content_sha256,
    )


async def store_staged_direct_attachment_upload(
    *,
    staged_path: str,
    staged_size: int,
    staged_sha256: str,
    declared_content_type: str | None,
    display_name: str,
    storage_root: str,
    max_bytes: int,
    storage_manager: StorageManagerProtocol,
    token_collection: TokenCollectionProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    cancellation_id: str,
) -> StoredDirectAttachmentUpload:
    safe_filename = secure_filename(display_name)
    if not safe_filename:
        await cleanup_upload_artifacts(temp_path=staged_path, permanent_path=None)
        raise ValidationError("display_name is invalid.")
    file_id = f"file-{uuid.uuid4().hex}"
    permanent_path = os.path.join(storage_root, f"{file_id}_{safe_filename}")
    try:
        validated_size = _validate_declared_size(staged_size, max_bytes=max_bytes)
        if validated_size is None or validated_size != staged_size:
            raise ValidationError("Staged attachment size is invalid.")
        actual_size = await asyncio.to_thread(os.path.getsize, staged_path)
        if actual_size != staged_size:
            raise ValidationError("Staged attachment size changed before storage.")
        await move_direct_attachment_to_storage(
            temp_path=staged_path,
            permanent_path=permanent_path,
            size_bytes=staged_size,
            storage_manager=storage_manager,
            token_collection=token_collection,
            cancellation_history=cancellation_history,
            cancellation_event_bus=cancellation_event_bus,
            cancellation_id=cancellation_id,
        )
    except asyncio.CancelledError:
        await cleanup_upload_artifacts(temp_path=staged_path, permanent_path=permanent_path)
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        await cleanup_upload_artifacts(temp_path=staged_path, permanent_path=permanent_path)
        raise coerce_to_soai_error(
            exception,
            operation=OPERATION_DIRECT_ATTACHMENT_UPLOAD_FAILURE,
        ) from exception
    return build_stored_direct_attachment_upload(
        file_id=file_id,
        permanent_path=permanent_path,
        safe_filename=safe_filename,
        declared_content_type=declared_content_type,
        size_bytes=staged_size,
        content_sha256=staged_sha256,
    )
