"""SoAI - Cancellation-scoped single-file upload request staging [backend/features/api/routes/upload_streaming_single_file_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.files.upload_policy import resolve_temp_directory_path
from core.logging.protocols import TraceLogger
from core.tasks.cancellation_token_scope import cancellation_token_scope
from features.api.routes.upload_streaming_multipart import (
    parse_and_stage_single_file_multipart,
)
from features.api.routes.upload_streaming_multipart_models import (
    StreamingMultipartResult,
)
from features.api.routes.upload_streaming_reservations import (
    StreamingUploadReservationPurpose,
    StreamingUploadReservationTracker,
)
from features.api.runtime.context import get_request_trace_id
from features.api.runtime.request_cancellation import (
    resolve_request_cancellation_id_or_create,
)

if TYPE_CHECKING:
    from fastapi import Request

    from features.api.runtime.context import ApiContext

__all__ = (
    "SingleFileUploadRequestSpec",
    "StagedSingleFileUploadRequest",
    "stage_single_file_upload_request",
)

SINGLE_FILE_UPLOAD_METADATA_LIMIT_BYTES = 65_536


@dataclass(frozen=True, slots=True)
class SingleFileUploadRequestSpec:
    subsystem: str
    owner: str
    logger: TraceLogger
    reservation_purpose: StreamingUploadReservationPurpose
    required_fields: frozenset[str]
    allowed_fields: frozenset[str]
    maximum_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class StagedSingleFileUploadRequest:
    parsed: StreamingMultipartResult
    cancellation_id: str


async def stage_single_file_upload_request(
    request: Request,
    *,
    api_context: ApiContext,
    spec: SingleFileUploadRequestSpec,
) -> StagedSingleFileUploadRequest:
    temp_dir = resolve_temp_directory_path(
        api_context.dependencies.config,
        api_context.dependencies.files,
    )
    reservation_tracker = StreamingUploadReservationTracker(
        storage_manager=api_context.dependencies.storage_manager,
        temp_dir=temp_dir,
        initial_purpose=spec.reservation_purpose,
    )
    cancellation_id = resolve_request_cancellation_id_or_create(
        request,
        subsystem=spec.subsystem,
        trace_id=get_request_trace_id(request),
        owner=spec.owner,
    )
    async with cancellation_token_scope(
        api_context.dependencies.token_collection,
        api_context.dependencies.cancellation_history,
        api_context.dependencies.cancellation_event_bus,
        cancellation_id=cancellation_id,
        owner=spec.owner,
        metadata={},
    ) as token:
        parsed = await parse_and_stage_single_file_multipart(
            request,
            parser_semaphore=api_context.dependencies.multipart_parser_semaphore,
            required_fields=spec.required_fields,
            allowed_fields=spec.allowed_fields,
            temp_dir=temp_dir,
            max_file_bytes=_maximum_file_bytes(api_context, spec.maximum_bytes),
            max_field_bytes=SINGLE_FILE_UPLOAD_METADATA_LIMIT_BYTES,
            token=token,
            reservation_controller=reservation_tracker,
            logger=spec.logger,
        )
    return StagedSingleFileUploadRequest(parsed=parsed, cancellation_id=cancellation_id)


def _maximum_file_bytes(api_context: ApiContext, requested_maximum: int | None) -> int:
    configured = resolve_upload_limit_bytes(
        api_context.dependencies.config,
        UploadLimitType.FILE,
    )
    return configured if requested_maximum is None else min(configured, requested_maximum)
