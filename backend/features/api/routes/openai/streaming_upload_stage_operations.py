"""SoAI - OpenAI streaming upload staging operations [backend/features/api/routes/openai/streaming_upload_stage_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, NoReturn

from fastapi import Request

from core.events.types_base import Event
from core.logging.trace import get_logger
from core.progress.speed import SpeedCalculator
from core.runtime.request_source_resolution import resolve_request_source_for_request
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.tasks.enums import TaskStatus
from core.tasks.protocols import TaskRegistryProtocol
from features.api.routes.openai.streaming_upload_error_handling import (
    finalize_cleanup_and_raise,
)
from features.api.routes.openai.streaming_upload_stage_progress import UploadProgressReporter
from features.api.routes.upload_progress_reporting import UploadProgressState
from features.api.routes.upload_streaming_multipart import (
    parse_and_stage_streaming_multipart,
)
from features.api.routes.upload_streaming_multipart_models import (
    StreamingMultipartResult,
    StreamingMultipartSpec,
)
from features.api.routes.upload_streaming_progress import (
    StreamingProgressBridge,
    build_ignore_multipart_bytes_reporter,
)
from features.api.routes.upload_streaming_reservations import (
    StreamingUploadReservationPurpose,
    StreamingUploadReservationTracker,
)
from features.api.runtime.task_metadata import build_command_task_metadata
from features.api.runtime.task_preparation import (
    create_dispatch_task,
)

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.tasks.task import Task
    from core.types.json import JSONValue
    from features.api.runtime.context import ApiContext

__all__ = (
    "build_upload_progress_bridge",
    "close_bridge_finalize_and_raise",
    "create_dispatch_task_for_upload",
    "stage_multipart_with_progress",
)

LOGGER_NAME_API_OPENAI_UPLOAD_PROGRESS = "SoAI.features.api.openai_upload_progress"
LOGGER_NAME_FEATURES_API_ROUTES_OPENAI = "SoAI.features.api.routes_openai"


async def create_dispatch_task_for_upload(
    request: Request,
    *,
    registry: TaskRegistryProtocol,
    command_type: type[Event],
    audit_action: str,
    audit_target: str,
    audit_details: Mapping[str, JSONValue] | None,
) -> tuple[Task, asyncio.Queue[Event]]:
    task_metadata = build_command_task_metadata(
        request,
        command_type,
        audit_action,
        audit_target,
        audit_details,
        {},
    )
    task, reply_queue = await create_dispatch_task(
        request,
        registry,
        command_type,
        task_metadata,
        request_source=resolve_request_source_for_request(request),
        delivery_mode="blocking",
    )
    return task, reply_queue


def build_upload_progress_bridge(
    *,
    registry: TaskRegistryProtocol,
    task_id: str,
    total_stream_bytes: int | None,
    operation: str,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    cancellation_id: str,
    owner: str,
) -> StreamingProgressBridge:
    reporter = UploadProgressReporter(
        registry=registry,
        task_id=task_id,
        total_stream_bytes=total_stream_bytes,
        upload_state=UploadProgressState(speed_calculator=SpeedCalculator()),
    )
    return StreamingProgressBridge(
        callback=reporter.report,
        logger=get_logger(LOGGER_NAME_API_OPENAI_UPLOAD_PROGRESS),
        operation=f"api_openai.{operation}.upload_progress",
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        cancellation_id=cancellation_id,
        owner=owner,
    )


async def stage_multipart_with_progress(
    request: Request,
    *,
    api_context: ApiContext,
    bridge: StreamingProgressBridge,
    cancellation_id: str,
    operation: str,
    spec: StreamingMultipartSpec,
    total_stream_bytes: int | None,
) -> tuple[StreamingMultipartResult, list[str]]:
    staged_paths: list[str] = []
    reservation_purpose = StreamingUploadReservationPurpose(
        declared_operation=f"api_openai.{operation}.upload_temp_stream",
        chunk_operation=f"api_openai.{operation}.upload_temp_chunk",
        declared_details={
            "purpose": "openai_upload_temp",
            "temp_directory": spec.temp_dir,
            "declared_stream_size": total_stream_bytes,
        },
        chunk_details={
            "purpose": "openai_upload_temp",
            "temp_directory": spec.temp_dir,
        },
    )
    reservation_tracker = StreamingUploadReservationTracker(
        storage_manager=api_context.dependencies.storage_manager,
        temp_dir=spec.temp_dir,
        initial_purpose=reservation_purpose,
    )

    bridge.start()
    try:
        if total_stream_bytes is not None and total_stream_bytes > 0:
            reservation_tracker.reserve_declared_remainder(
                declared_size=total_stream_bytes,
            )
        async with cancellation_token_scope(
            api_context.dependencies.token_collection,
            api_context.dependencies.cancellation_history,
            api_context.dependencies.cancellation_event_bus,
            cancellation_id=cancellation_id,
            owner=f"openai_upload:{operation}",
            metadata={},
        ) as token:
            parsed = await parse_and_stage_streaming_multipart(
                request,
                parser_semaphore=api_context.dependencies.multipart_parser_semaphore,
                spec=spec,
                token=token,
                report_bytes=build_ignore_multipart_bytes_reporter(),
                report_field=None,
                report_stream_bytes=bridge.report,
                write_controller=reservation_tracker,
                logger=get_logger(LOGGER_NAME_FEATURES_API_ROUTES_OPENAI),
            )
    finally:
        reservation_tracker.release_active_reservation()
    staged_paths.extend(part.temp_path for part in parsed.files)
    await bridge.close(final_bytes_done=reservation_tracker.written_bytes)
    return parsed, staged_paths


async def close_bridge_finalize_and_raise(
    request: Request,
    *,
    bridge: StreamingProgressBridge,
    registry: TaskRegistryProtocol,
    task_id: str,
    task_status: TaskStatus,
    http_status: int,
    error_type: str,
    error_message: str,
    staged_paths: list[str],
) -> NoReturn:
    await bridge.close()
    await finalize_cleanup_and_raise(
        request,
        registry=registry,
        task_id=task_id,
        task_status=task_status,
        http_status=http_status,
        error_type=error_type,
        error_message=error_message,
        staged_paths=staged_paths,
    )
