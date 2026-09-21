"""SoAI - Provider projection for WebUI file attachments [backend/features/api/runtime/webui_attachments/file_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from core.attachments.attachment_content_validation import (
    validate_soai_file_content_part,
)
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import ValidationError
from core.files.managed_storage_errors import FileStorageSecurityError
from features.api.runtime.webui_attachments.physical_file_snapshot import (
    load_soai_file_attachment,
    load_soai_file_record,
)
from features.api.runtime.webui_attachments.physical_file_text_projection import (
    file_content_header,
    file_identity_available,
    pending_file_text_part,
    ready_file_text_part,
)
from features.api.runtime.webui_attachments.provider_descriptor_snapshot import (
    close_provider_descriptor_snapshot,
)
from features.api.runtime.webui_attachments.provider_image_projection import (
    shape_descriptor_image_for_provider,
)
from features.api.runtime.webui_attachments.provider_text_rendering import (
    build_file_content_unavailable_text,
    build_missing_text_extraction_text,
)
from features.api.runtime.webui_attachments.provider_video_budget import (
    provider_video_part_key,
)
from features.api.runtime.webui_attachments.verified_provider_snapshot import (
    load_verified_provider_descriptor_snapshot,
)

if TYPE_CHECKING:
    from core.files.database_types import FileCatalogRecordWithPath
    from core.types.json import JSONDict
    from features.api.runtime.webui_attachments.projection_context import (
        WebuiAttachmentProjectionContext,
    )

__all__ = ("project_soai_file_for_provider",)

_VALID_PARSE_STATES = frozenset(("pending", "ready", "failed"))


def _require_parse_state(attachment: JSONDict) -> str:
    parse_state = attachment.get("parse_state")
    if not isinstance(parse_state, str) or parse_state not in _VALID_PARSE_STATES:
        raise ValidationError("SoAI file attachment parse_state is invalid.")
    return parse_state


def _unavailable_part(attachment: JSONDict, *, reason: str) -> list[JSONDict]:
    return [
        {
            "type": "text",
            "text": build_file_content_unavailable_text(
                header=file_content_header(attachment),
                reason=reason,
            ),
        },
    ]


def _video_note(reason: str | None) -> list[JSONDict]:
    if reason is None:
        return []
    return [{"type": "text", "text": reason}]


async def _project_video_parts(
    context: WebuiAttachmentProjectionContext,
    *,
    record: FileCatalogRecordWithPath,
    attachment: JSONDict,
    canonical_part: JSONDict,
) -> tuple[list[JSONDict], str | None]:
    projection_key = provider_video_part_key(canonical_part)
    allocation = (
        context.video_allocations.get(projection_key) if projection_key is not None else None
    )
    if allocation is None:
        return ([], "Video frames were omitted by the request projection limit.")
    try:
        snapshot = await load_verified_provider_descriptor_snapshot(
            context.storage_root,
            record=record,
            attachment=attachment,
        )
    except FileStorageSecurityError:
        return ([], "Attachment file is unavailable.")
    if snapshot is None:
        return ([], "Attachment file content changed.")
    try:
        projected = await context.video_session.project_video(
            content_identity=(f"{record['content_sha256']}:{record['size_bytes']}"),
            source_path=snapshot.temp_path,
            allocation=allocation,
        )
    finally:
        close_provider_descriptor_snapshot(snapshot)
    return (projected.copy_parts(), projected.reason)


async def _identity_unavailable_part(
    context: WebuiAttachmentProjectionContext,
    *,
    record: FileCatalogRecordWithPath,
    attachment: JSONDict,
) -> list[JSONDict] | None:
    if await file_identity_available(context, record=record, attachment=attachment):
        return None
    return _unavailable_part(attachment, reason="Attachment file is unavailable.")


async def project_soai_file_for_provider(
    context: WebuiAttachmentProjectionContext,
    *,
    part: JSONDict,
) -> list[JSONDict]:
    canonical_part = validate_soai_file_content_part(part)
    attachment = await load_soai_file_attachment(
        context.dependencies.database_conversation_attachments,
        conv_id=context.conv_id,
        user_id=context.user_id,
        part=canonical_part,
    )
    if attachment is None:
        return _unavailable_part(canonical_part, reason="Attachment is unavailable.")
    record = await load_soai_file_record(
        context.dependencies.database_files,
        user_id=context.user_id,
        attachment=attachment,
    )
    if record is None:
        return _unavailable_part(attachment, reason="Attachment file is unavailable.")
    parse_state = _require_parse_state(attachment)
    provider_text = attachment.get("provider_text")
    video_parts: list[JSONDict] = []
    video_reason: str | None = None
    if attachment.get("preview_type") == "video" and context.vision_supported:
        video_parts, video_reason = await _project_video_parts(
            context,
            record=record,
            attachment=attachment,
            canonical_part=canonical_part,
        )
        if (
            video_reason in {"Attachment file is unavailable.", "Attachment file content changed."}
            and not video_parts
        ):
            return _unavailable_part(attachment, reason=video_reason)
    image_shape_failure_reason: str | None = None
    if attachment.get("preview_type") == "image" and context.vision_supported:
        try:
            snapshot = await load_verified_provider_descriptor_snapshot(
                context.storage_root,
                record=record,
                attachment=attachment,
            )
        except FileStorageSecurityError:
            return _unavailable_part(attachment, reason="Attachment file is unavailable.")
        if snapshot is None:
            return _unavailable_part(attachment, reason="Attachment file content changed.")
        try:
            image_shaper = partial(
                shape_descriptor_image_for_provider,
                descriptor=snapshot.descriptor,
                declared_content_type=str(attachment.get("mime_type") or ""),
                config=context.dependencies.config,
                max_encoded_chars=context.dependencies.config.get_int(
                    "SERVER.WEBUI.PROVIDER_IMAGE.MAX_ENCODED_CHARS",
                ),
            )
            shaped = await run_joined_thread_call(
                image_shaper,
                task_name="webui-attachment-provider-image-shape",
            )
        finally:
            close_provider_descriptor_snapshot(snapshot)
        if shaped.part is not None:
            return [shaped.part]
        image_shape_failure_reason = shaped.failure_reason
        if isinstance(provider_text, str) and provider_text.strip():
            return [
                ready_file_text_part(context, attachment=attachment, provider_text=provider_text),
            ]
    if parse_state == "ready" and isinstance(provider_text, str) and provider_text.strip():
        unavailable = await _identity_unavailable_part(
            context,
            record=record,
            attachment=attachment,
        )
        if unavailable is not None:
            return unavailable
        return [
            ready_file_text_part(context, attachment=attachment, provider_text=provider_text),
            *video_parts,
            *_video_note(video_reason),
        ]
    if parse_state == "failed":
        unavailable = await _identity_unavailable_part(
            context,
            record=record,
            attachment=attachment,
        )
        if unavailable is not None:
            return unavailable
        return [
            {
                "type": "text",
                "text": build_file_content_unavailable_text(
                    header=file_content_header(attachment),
                    reason=str(attachment.get("parse_error") or ""),
                ),
            },
            *video_parts,
            *_video_note(video_reason),
        ]
    if attachment.get("preview_type") == "image" and not context.vision_supported:
        unavailable = await _identity_unavailable_part(
            context,
            record=record,
            attachment=attachment,
        )
        if unavailable is not None:
            return unavailable
        return _unavailable_part(attachment, reason="Model vision input is unavailable.")
    if image_shape_failure_reason is not None:
        return _unavailable_part(attachment, reason=image_shape_failure_reason)
    if parse_state == "ready":
        unavailable = await _identity_unavailable_part(
            context,
            record=record,
            attachment=attachment,
        )
        if unavailable is not None:
            return unavailable
        return [
            {
                "type": "text",
                "text": build_missing_text_extraction_text(header=file_content_header(attachment)),
            },
            *video_parts,
            *_video_note(video_reason),
        ]
    try:
        return [
            await pending_file_text_part(context, record=record, attachment=attachment),
            *video_parts,
            *_video_note(video_reason),
        ]
    except FileStorageSecurityError:
        return _unavailable_part(attachment, reason="Attachment file is unavailable.")
