"""SoAI - Provider file projection for WebUI SoAI path attachments [backend/features/api/runtime/webui_attachments/soai_path_file_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from functools import partial
from typing import TYPE_CHECKING

from core.attachments.attachment_parse_classification import (
    classify_attachment_descriptor_for_provider,
)
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import ValidationError
from core.files.document_type_detection import extract_extension, is_image_type
from core.timing.constants import YIELD_CONTROL_SEC
from core.users.ocr_preferences import resolve_user_ocr_language
from core.validation.integers import is_strict_int
from core.workspaces.soai_path_part_fields import target_fingerprint_value
from features.api.runtime.webui_attachments.provider_descriptor_snapshot import (
    close_provider_descriptor_snapshot,
    load_provider_descriptor_snapshot,
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
from features.api.runtime.webui_attachments.soai_path_provider_text import (
    build_soai_path_file_content_text,
    build_soai_path_reference_text,
    build_soai_path_unavailable_text,
    require_soai_path_projection_str,
    resolve_optional_soai_path_title,
)
from features.api.runtime.webui_attachments.soai_path_snapshot import (
    open_verified_soai_path_file_descriptor,
)

if TYPE_CHECKING:
    from core.attachments.attachment_parse_classification import AttachmentParseOutcome
    from core.types.json import JSONDict
    from features.api.runtime.webui_attachments.projection_context import (
        WebuiAttachmentProjectionContext,
    )
    from features.api.runtime.webui_attachments.provider_descriptor_snapshot import (
        ProviderDescriptorSnapshot,
    )

__all__ = ("project_soai_path_file_for_provider",)

READ_TIMEOUT_SEC_KEY = "SERVER.WEBUI.SOAI_LINKS.PROJECTION_READ_TIMEOUT_SEC"


def _close_cancelled_snapshot(snapshot: ProviderDescriptorSnapshot | None) -> None:
    if snapshot is not None:
        close_provider_descriptor_snapshot(snapshot)


def _unavailable_part(canonical: JSONDict) -> list[JSONDict]:
    return [
        {
            "type": "text",
            "text": build_soai_path_unavailable_text(
                title=resolve_optional_soai_path_title(canonical),
                note="Live target changed since attachment.",
            ),
        },
    ]


def _video_note(reason: str | None) -> list[JSONDict]:
    return [] if reason is None else [{"type": "text", "text": reason}]


async def _snapshot_descriptor(
    *,
    canonical: JSONDict,
    effective_root: str,
    title: str,
    size_bytes: int,
) -> ProviderDescriptorSnapshot | None:
    source_descriptor = open_verified_soai_path_file_descriptor(
        effective_root=effective_root,
        canonical=canonical,
    )
    if source_descriptor is None:
        return None
    try:
        snapshot_loader = partial(
            load_provider_descriptor_snapshot,
            source_descriptor=source_descriptor,
            filename=title,
            expected_size_bytes=size_bytes,
            expected_sha256=target_fingerprint_value(canonical).removeprefix("sha256:"),
        )
        return await run_joined_thread_call(
            snapshot_loader,
            task_name="webui-soai-path-provider-snapshot",
            cancelled_result_cleanup=_close_cancelled_snapshot,
        )
    finally:
        os.close(source_descriptor)


async def project_soai_path_file_for_provider(
    context: WebuiAttachmentProjectionContext,
    *,
    canonical: JSONDict,
    effective_root: str,
) -> list[JSONDict]:
    mime_type = require_soai_path_projection_str(canonical.get("mime_type"), field="mime_type")
    title = require_soai_path_projection_str(canonical.get("title"), field="title")
    size_bytes = canonical.get("size_bytes")
    if not is_strict_int(size_bytes):
        raise ValidationError("WebUI SoAI path projection field 'size_bytes' must be an integer.")
    image = is_image_type(mime_type, extract_extension(title))
    video = canonical.get("preview_type") == "video"
    snapshot = await _snapshot_descriptor(
        canonical=canonical,
        effective_root=effective_root,
        title=title,
        size_bytes=size_bytes,
    )
    if snapshot is None:
        return _unavailable_part(canonical)
    image_shape_failure_reason: str | None = None
    video_parts: list[JSONDict] = []
    video_reason: str | None = None
    try:
        if image and context.vision_supported:
            image_shaper = partial(
                shape_descriptor_image_for_provider,
                descriptor=snapshot.descriptor,
                declared_content_type=mime_type,
                config=context.dependencies.config,
                max_encoded_chars=context.dependencies.config.get_int(
                    "SERVER.WEBUI.PROVIDER_IMAGE.MAX_ENCODED_CHARS",
                ),
            )
            shaped = await run_joined_thread_call(
                image_shaper,
                task_name="webui-soai-path-provider-image-shape",
            )
            if shaped.part is not None:
                return [shaped.part]
            image_shape_failure_reason = shaped.failure_reason
        content_identity = f"{target_fingerprint_value(canonical)}:{size_bytes}"
        if video and context.vision_supported:
            projection_key = provider_video_part_key(canonical)
            allocation = (
                context.video_allocations.get(projection_key)
                if projection_key is not None
                else None
            )
            if allocation is None:
                video_reason = "Video frames were omitted by the request projection limit."
            else:
                video_projection = await context.video_session.project_video(
                    content_identity=content_identity,
                    source_path=snapshot.temp_path,
                    allocation=allocation,
                )
                video_parts = video_projection.copy_parts()
                video_reason = video_projection.reason

        async def classify_file() -> AttachmentParseOutcome:
            return await classify_attachment_descriptor_for_provider(
                ocr_language=await resolve_user_ocr_language(
                    context.dependencies.database_users, context.user_id
                ),
                document_reader=context.dependencies.document_reader,
                parser_registry_factory=context.dependencies.parser_registry_factory,
                descriptor=snapshot.descriptor,
                filename=title,
                mime_type=mime_type,
                max_chars=context.provider_text_char_budget,
                parse_timeout_sec=context.dependencies.config.get_float(READ_TIMEOUT_SEC_KEY),
            )

        outcome = (
            await context.video_session.classify_linked_video(
                content_identity=content_identity,
                classify=classify_file,
            )
            if video
            else await classify_file()
        )
    finally:
        close_provider_descriptor_snapshot(snapshot)
        await asyncio.sleep(YIELD_CONTROL_SEC)
    if outcome.provider_text is not None and outcome.provider_text.strip():
        return [
            {
                "type": "text",
                "text": build_soai_path_file_content_text(
                    canonical,
                    outcome.provider_text.strip(),
                    truncated=bool(outcome.provider_text_truncated),
                ),
            },
            *video_parts,
            *_video_note(video_reason),
        ]
    header = build_soai_path_reference_text(canonical)
    if outcome.parse_state == "failed":
        return [
            {
                "type": "text",
                "text": build_file_content_unavailable_text(
                    header=header,
                    reason=outcome.parse_error,
                ),
            },
            *video_parts,
            *_video_note(video_reason),
        ]
    if image:
        image_note = image_shape_failure_reason
        if image_note is None and not context.vision_supported:
            image_note = "Model vision input is unavailable."
        return [
            {
                "type": "text",
                "text": build_soai_path_reference_text(
                    canonical,
                    note=image_note
                    or "Linked image is over the configured provider image size limit.",
                ),
            },
        ]
    return [
        {"type": "text", "text": build_missing_text_extraction_text(header=header)},
        *video_parts,
        *_video_note(video_reason),
    ]
