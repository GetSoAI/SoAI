"""SoAI - RAG document upload setup helpers [backend/features/api/routes/webui/conversation_rag/documents/upload/setup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.errors.exceptions import ValidationError
from core.files.upload_policy import resolve_temp_directory_runtime
from core.logging.protocols import StandardLogger
from core.logging.trace import get_logger
from core.progress.speed import SpeedCalculator
from core.runtime.ownership import resolve_context_ownership
from core.runtime.request_context import RequestContext
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from core.tasks.type_catalog import TASK_TYPE_RAG_DOCUMENT_UPLOAD
from features.api.routes.upload_streaming_progress import StreamingProgressBridge
from features.api.routes.upload_streaming_reservations import StreamingUploadReservationTracker
from features.api.routes.webui.conversation_rag.documents.staging import (
    build_rag_document_reservation_purpose,
)
from features.api.routes.webui.conversation_rag.documents.upload.staging_progress_reporter import (
    RagDocumentStagingProgressReporter,
)
from features.api.routes.webui.conversation_rag.ingest_preflight import (
    resolve_conversation_rag_ingest_preflight,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_server_error
from features.api.runtime.task_registry import require_task_registry_or_raise
from features.api.runtime.webui_records import webui_fetch_or_404

if TYPE_CHECKING:
    from fastapi import Request

    from core.mcp.protocols_rag import MCPRAGProtocol
    from core.tasks.protocols import TaskRegistryProtocol

__all__ = (
    "RagDocumentUploadSetup",
    "prepare_rag_document_upload",
)

LOGGER_NAME = "SoAI.features.api.setup"
LOGGER_NAME_UPLOAD_PROGRESS = "SoAI.features.api.upload_progress"


@dataclass(frozen=True, slots=True)
class RagDocumentUploadSetup:
    rag_engine: MCPRAGProtocol
    resolved_id: str
    temp_dir: str
    max_upload_bytes: int
    registry: TaskRegistryProtocol
    task: Task
    context: RequestContext
    bridge: StreamingProgressBridge
    reservation_tracker: StreamingUploadReservationTracker
    logger: StandardLogger


async def prepare_rag_document_upload(
    request: Request,
    *,
    conv_id: str,
    user_id: int,
    api_context: ApiContext,
) -> RagDocumentUploadSetup:
    logger = get_logger(LOGGER_NAME)
    await webui_fetch_or_404(
        request,
        api_context.dependencies.database_conversations.get_conversation(conv_id, user_id),
        message="Conversation not found.",
    )
    rag_engine, resolved_id = await resolve_conversation_rag_ingest_preflight(
        request=request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
        reindex_error_verb="upload documents",
    )
    try:
        temp_dir = resolve_temp_directory_runtime(api_context.dependencies.config)
    except ValidationError as exception:
        raise_server_error(request, str(exception))
    max_upload_bytes = resolve_upload_limit_bytes(
        api_context.dependencies.config,
        UploadLimitType.FILE,
    )
    registry = await require_task_registry_or_raise(request, api_context.dependencies)
    context = request.state.context
    cancellation_id = resolve_context_ownership(context).cancellation_id
    task = await create(
        registry,
        task_type=TASK_TYPE_RAG_DOCUMENT_UPLOAD,
        user_id=user_id,
        owner_id=resolved_id,
        owner_type="conversation",
        cancellation_id=cancellation_id,
        status=TaskStatus.WORKING,
        progress_total=100,
        status_message="Uploading document",
        metadata={
            "operation": "conversation_rag.document_upload",
            "conv_id": resolved_id,
            "filename": "",
        },
    )
    context.task_id = task.task_id
    reservation_tracker = StreamingUploadReservationTracker(
        storage_manager=api_context.dependencies.storage_manager,
        temp_dir=temp_dir,
        initial_purpose=build_rag_document_reservation_purpose("document", resolved_id),
        initial_filename="document",
        purpose_for_filename=lambda filename: build_rag_document_reservation_purpose(
            filename,
            resolved_id,
        ),
    )
    reporter = RagDocumentStagingProgressReporter(
        registry=registry,
        task_id=task.task_id,
        logger=logger,
        speed_calculator=SpeedCalculator(),
        reservation_tracker=reservation_tracker,
    )
    bridge = StreamingProgressBridge(
        callback=reporter.report,
        logger=get_logger(LOGGER_NAME_UPLOAD_PROGRESS),
        operation="webui.conversation_rag.upload_document.progress",
        cancellation_binder=api_context.dependencies.task_cancellation_binder,
        finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
        cancellation_id=cancellation_id,
        owner="rag_document_upload_progress",
    )
    return RagDocumentUploadSetup(
        rag_engine=rag_engine,
        resolved_id=resolved_id,
        temp_dir=temp_dir,
        max_upload_bytes=max_upload_bytes,
        registry=registry,
        task=task,
        context=context,
        bridge=bridge,
        reservation_tracker=reservation_tracker,
        logger=logger,
    )
