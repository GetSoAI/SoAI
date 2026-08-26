"""SoAI - Physical attachment streaming upload staging [backend/features/api/routes/webui/conversation_attachments/physical_upload_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from features.api.routes.upload_streaming_multipart_models import StreamingStagedPart
from features.api.routes.upload_streaming_reservations import (
    StreamingUploadReservationPurpose,
)
from features.api.routes.upload_streaming_single_file_request import (
    SingleFileUploadRequestSpec,
    stage_single_file_upload_request,
)

if TYPE_CHECKING:
    from fastapi import Request

    from features.api.runtime.context import ApiContext

__all__ = ("PhysicalAttachmentStagedUpload", "stage_physical_attachment_upload")

LOGGER_NAME = "SoAI.features.api.physical_upload_staging"
_ATTACHMENT_FIELDS = frozenset(
    {"display_name", "source", "client_attachment_id", "client_request_id"}
)


@dataclass(frozen=True, slots=True)
class PhysicalAttachmentStagedUpload:
    part: StreamingStagedPart
    display_name: str
    source: str
    client_attachment_id: str
    client_request_id: str
    cancellation_id: str


def _required_field(fields: dict[str, tuple[str, ...]], name: str) -> str:
    values = fields.get(name)
    if values is None or len(values) != 1:
        raise ValidationError(f"Missing required multipart field '{name}'.")
    return values[0]


async def stage_physical_attachment_upload(
    request: Request,
    *,
    api_context: ApiContext,
) -> PhysicalAttachmentStagedUpload:
    staged = await stage_single_file_upload_request(
        request,
        api_context=api_context,
        spec=SingleFileUploadRequestSpec(
            subsystem="attachment_upload",
            owner="physical_attachment_upload",
            logger=get_logger(LOGGER_NAME),
            reservation_purpose=StreamingUploadReservationPurpose(
                declared_operation="webui.conversation_attachment.stage",
                chunk_operation="webui.conversation_attachment.stage_chunk",
                declared_details={"purpose": "conversation_attachment_upload"},
                chunk_details={"purpose": "conversation_attachment_upload"},
            ),
            required_fields=_ATTACHMENT_FIELDS,
            allowed_fields=_ATTACHMENT_FIELDS,
        ),
    )
    fields = staged.parsed.fields
    return PhysicalAttachmentStagedUpload(
        part=staged.parsed.files[0],
        display_name=_required_field(fields, "display_name"),
        source=_required_field(fields, "source"),
        client_attachment_id=_required_field(fields, "client_attachment_id"),
        client_request_id=_required_field(fields, "client_request_id"),
        cancellation_id=staged.cancellation_id,
    )
