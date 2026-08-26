"""SoAI - Conversation PDF export upload staging [backend/features/api/routes/webui/conversation_pdf_export_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import PayloadTooLargeError, ValidationError
from core.files.upload_size_validation import (
    ensure_staged_size_matches_declared,
    parse_size_bytes_field,
)
from core.files.upload_staging import cleanup_temp_file
from core.filesystem.atomic_writes import atomic_write_text_content
from core.logging.trace import get_logger
from core.tasks.cancellation_token_scope import cancellation_token_scope
from features.api.routes.upload_streaming_multipart import (
    parse_and_stage_streaming_multipart,
)
from features.api.routes.upload_streaming_multipart_models import (
    StreamingMultipartResult,
)
from features.api.routes.upload_streaming_multipart_specs import (
    build_streaming_multipart_spec,
)
from features.api.routes.upload_streaming_reservations import (
    StreamingUploadReservationPurpose,
    StreamingUploadReservationTracker,
)

if TYPE_CHECKING:
    from fastapi import Request

    from core.tasks.task import Task
    from features.api.runtime.context import ApiContext
    from features.conversation_export.artifacts import ConversationPdfArtifactPaths
    from features.conversation_export.settings import ConversationPdfExportSettings

__all__ = (
    "ConversationPdfStagedUpload",
    "stage_conversation_pdf_export_upload",
)

LOGGER_NAME = "SoAI.features.api.conversation_pdf_export_staging"
CONVERSATION_PDF_EXPORT_METADATA_ALLOWANCE_BYTES = 8 * MIB_BYTES
_REQUIRED_FIELDS = frozenset(
    {
        "size_bytes",
        "title",
        "export_date",
        "small_logo_data_uri",
        "conversation_id",
        "expected_last_modified_at_ms",
        "cover_html",
        "footer_note_label",
        "footer_pages_label",
    },
)
_OPTIONAL_FIELDS = frozenset({"content_type", "cover_sha256", "html_sha256"})


@dataclass(frozen=True, slots=True)
class ConversationPdfStagedUpload:
    html_path: str
    html_size_bytes: int
    html_sha256: str
    cover_html_path: str
    cover_sha256: str
    fields: dict[str, tuple[str, ...]]


def _require_html_content_type(content_type: str | None) -> None:
    normalized = str(content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if normalized not in {"text/html", "application/xhtml+xml"}:
        raise ValidationError("PDF export upload must be an HTML document.")


def _require_cover_html(fields: dict[str, tuple[str, ...]]) -> str:
    values = fields.get("cover_html")
    if values is None or len(values) != 1:
        raise ValidationError("PDF export field 'cover_html' must be provided exactly once.")
    cover_html = values[0]
    if not cover_html.strip():
        raise ValidationError("Missing PDF export field 'cover_html'.")
    return cover_html


async def _stage_cover_document(
    fields: dict[str, tuple[str, ...]],
    cover_html_path: str,
) -> str:
    cover_html = _require_cover_html(fields)
    await asyncio.to_thread(atomic_write_text_content, cover_html_path, cover_html)
    return hashlib.sha256(cover_html.encode("utf-8")).hexdigest()


async def stage_conversation_pdf_export_upload(
    *,
    request: Request,
    api_context: ApiContext,
    task: Task,
    settings: ConversationPdfExportSettings,
    paths: ConversationPdfArtifactPaths,
) -> ConversationPdfStagedUpload:
    purpose = StreamingUploadReservationPurpose(
        declared_operation="webui.conversation_pdf_export.stage",
        chunk_operation="webui.conversation_pdf_export.stage_chunk",
        declared_details={"purpose": "conversation_pdf_export_html"},
        chunk_details={"purpose": "conversation_pdf_export_html"},
    )
    reservation_tracker = StreamingUploadReservationTracker(
        storage_manager=api_context.dependencies.storage_manager,
        temp_dir=settings.temp_dir,
        initial_purpose=purpose,
    )
    parsed: StreamingMultipartResult | None = None
    max_stream_bytes = settings.max_html_bytes + CONVERSATION_PDF_EXPORT_METADATA_ALLOWANCE_BYTES

    def on_declared_size(declared_size: int) -> None:
        reservation_tracker.reserve_declared_remainder(
            declared_size=declared_size,
            purpose=purpose,
        )

    def report_field(field_name: str, field_value: str) -> None:
        if field_name != "size_bytes":
            return
        on_declared_size(
            parse_size_bytes_field(field_value, max_upload_bytes=settings.max_html_bytes),
        )

    def report_stream_bytes(stream_bytes_done: int) -> None:
        if stream_bytes_done > max_stream_bytes:
            raise PayloadTooLargeError("PDF export request exceeds the configured maximum size.")

    try:
        async with cancellation_token_scope(
            api_context.dependencies.token_collection,
            api_context.dependencies.cancellation_history,
            api_context.dependencies.cancellation_event_bus,
            cancellation_id=task.cancellation_id,
            owner="conversation_pdf_export_upload",
            metadata={"task_id": task.task_id},
        ) as token:
            parsed = await parse_and_stage_streaming_multipart(
                request,
                parser_semaphore=api_context.dependencies.multipart_parser_semaphore,
                spec=build_streaming_multipart_spec(
                    required_fields=_REQUIRED_FIELDS,
                    allowed_fields=_REQUIRED_FIELDS | _OPTIONAL_FIELDS,
                    required_file_fields=frozenset({"file"}),
                    allowed_file_fields=frozenset({"file"}),
                    allow_multiple_files=False,
                    require_fields_before_files=True,
                    temp_dir=settings.temp_dir,
                    max_file_bytes=settings.max_html_bytes,
                    max_total_file_bytes=settings.max_html_bytes,
                ),
                token=token,
                report_bytes=lambda _bytes_done: None,
                report_field=report_field,
                report_stream_bytes=report_stream_bytes,
                logger=get_logger(LOGGER_NAME),
                write_controller=reservation_tracker,
            )
        if len(parsed.files) != 1:
            raise ValidationError("Exactly one PDF export HTML file must be uploaded.")
        part = parsed.files[0]
        declared_size = reservation_tracker.declared_size
        if declared_size is None:
            raise ValidationError("size_bytes must be declared before the PDF export file.")
        ensure_staged_size_matches_declared(
            declared_size=declared_size,
            staged_size=part.size_bytes,
        )
        _require_html_content_type(part.content_type)
        os.makedirs(paths.task_dir, exist_ok=True)
        await asyncio.to_thread(shutil.move, part.temp_path, paths.upload_path)
        cover_sha256 = await _stage_cover_document(parsed.fields, paths.cover_html_path)
        return ConversationPdfStagedUpload(
            html_path=paths.upload_path,
            html_size_bytes=part.size_bytes,
            html_sha256=part.content_sha256,
            cover_html_path=paths.cover_html_path,
            cover_sha256=cover_sha256,
            fields=parsed.fields,
        )
    finally:
        reservation_tracker.release_active_reservation()
        if parsed is not None:
            for part in parsed.files:
                if part.temp_path != paths.upload_path:
                    await cleanup_temp_file(part.temp_path)
