"""SoAI - Mail file loading and attachment upload helpers [backend/features/mail/file_uploads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.events.types_base import Event
from core.events.types_files import FileUploadCommand
from core.events.types_models_streaming import InferenceResultEvent
from core.events.types_plugins import ErrorEvent
from core.files.content_hashing import hash_file_content
from core.timing.constants import EXTENDED_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.files.database_types import FileCatalogRecordWithPath
    from core.files.protocols import DatabaseFilesProtocol
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict

__all__ = (
    "load_attachment_file_records",
    "upload_mail_attachment_file",
)


async def load_attachment_file_records(
    *,
    database_files: DatabaseFilesProtocol,
    user_id: int,
    file_ids: list[str],
) -> list[FileCatalogRecordWithPath]:
    records: list[FileCatalogRecordWithPath] = []
    for file_id in file_ids:
        record = await database_files.get_file_info_with_path(
            file_id,
            enforce_owner=True,
            user_id=user_id,
        )
        if record is None:
            raise ValidationError(f"Attachment file_id '{file_id}' was not found.")
        records.append(record)
    return records


async def upload_mail_attachment_file(
    *,
    event_bus: EventBusProtocol,
    request_context: RequestContext,
    temp_file_path: str,
    filename: str,
) -> JSONDict:
    reply_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=8)
    content_hash = await asyncio.to_thread(hash_file_content, temp_file_path)
    await event_bus.publish(
        FileUploadCommand(
            reply_channel=reply_queue,
            context=request_context,
            temp_file_path=temp_file_path,
            original_filename=filename,
            purpose="assistants",
            content_sha256=content_hash.sha256_hex,
            user_id=request_context.user_id,
            api_key_id=None,
        ),
    )
    event = await asyncio.wait_for(reply_queue.get(), timeout=float(EXTENDED_TIMEOUT_SEC))
    if isinstance(event, InferenceResultEvent):
        if isinstance(event.payload, dict):
            return dict(event.payload)
        raise StateError("Attachment upload response payload is invalid.")
    if isinstance(event, ErrorEvent):
        raise ValidationError(event.message)
    raise StateError("Attachment upload produced an unexpected reply event.")
