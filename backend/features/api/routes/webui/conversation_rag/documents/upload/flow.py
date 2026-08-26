"""SoAI - WebUI RAG document upload flow [backend/features/api/routes/webui/conversation_rag/documents/upload/flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import Request
from starlette.responses import Response

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    PayloadTooLargeError,
    RateLimitError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.rag_document_identity import normalize_rag_document_identity
from core.logging.trace import get_context_trace_id
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.tasks.task_cancellation import cancel
from features.api.routes.webui.conversation_rag.documents.staging import (
    stage_rag_document_upload,
)
from features.api.routes.webui.conversation_rag.documents.upload.cleanup import (
    finalize_rag_upload_cleanup,
)
from features.api.routes.webui.conversation_rag.documents.upload.error_handling import (
    handle_rag_document_upload_exception,
)
from features.api.routes.webui.conversation_rag.documents.upload.setup import (
    prepare_rag_document_upload,
)
from features.api.routes.webui.conversation_rag.knowledge_attachment_failures import (
    finalize_knowledge_attachment_task_failure,
)
from features.api.routes.webui.conversation_rag.knowledge_attachment_identity import (
    require_knowledge_attachment_id,
)
from features.api.routes.webui.conversation_rag.knowledge_attachment_lifecycle import (
    ensure_and_publish_knowledge_attachment,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.responses import create_json_response_with_task_id

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("handle_rag_document_upload",)

OPERATION_WEBUI_UPLOAD_RAG_DOCUMENT = "webui.conversation_rag.upload_document"
OPERATION_WEBUI_UPLOAD_RAG_DOCUMENT_CANCEL_AFTER_DISCONNECT = (
    "webui.conversation_rag.upload_document.cancel_after_disconnect"
)
HANDLED_RAG_DOCUMENT_UPLOAD_EXCEPTIONS: tuple[type[Exception], ...] = (
    TaskCancelledError,
    InsufficientDiskSpaceError,
    PayloadTooLargeError,
    RateLimitError,
    ValidationError,
    *RECOVERABLE_EXCEPTIONS,
)


async def handle_rag_document_upload(
    request: Request,
    *,
    conv_id: str,
    user_id: int,
    api_context: ApiContext,
    client_batch_id: str | None,
    attachment_source: str,
) -> Response:
    setup = await prepare_rag_document_upload(
        request,
        conv_id=conv_id,
        user_id=user_id,
        api_context=api_context,
    )
    temp_file_path: str | None = None
    content_size: int | None = None
    knowledge_summary: JSONDict | None = None
    try:
        async with cancellation_token_scope(
            api_context.dependencies.token_collection,
            api_context.dependencies.cancellation_history,
            api_context.dependencies.cancellation_event_bus,
            cancellation_id=setup.task.cancellation_id,
            owner="rag_document_upload",
            metadata={"conv_id": setup.resolved_id},
        ) as token:
            setup.bridge.start()
            temp_file_path, content_size = await stage_rag_document_upload(
                request,
                api_context=api_context,
                temp_dir=setup.temp_dir,
                max_upload_bytes=setup.max_upload_bytes,
                token=token,
                bridge=setup.bridge,
                reservation_tracker=setup.reservation_tracker,
            )
            await setup.bridge.close(final_bytes_done=content_size)
            token.raise_if_cancelled()
            document_identity = normalize_rag_document_identity(
                setup.reservation_tracker.current_filename,
                fallback_filename="document",
            )
            knowledge_summary = await ensure_and_publish_knowledge_attachment(
                api_context=api_context,
                conv_id=setup.resolved_id,
                user_id=user_id,
                source_type=attachment_source,
                operation_type="added",
                title=document_identity.filename,
                task_id=setup.task.task_id,
                client_batch_id=client_batch_id,
            )
            uploaded = await setup.rag_engine.upload_document_from_path(
                conv_id=setup.resolved_id,
                source_path=temp_file_path,
                filename=document_identity.filename,
                file_type=document_identity.file_type,
                user_id=user_id,
                existing_task_id=setup.task.task_id,
                transfer_progress_start=5,
                transfer_progress_end=9,
                knowledge_attachment_id=require_knowledge_attachment_id(knowledge_summary),
                knowledge_item_index=0,
                knowledge_source_type=attachment_source,
                knowledge_operation_type="added",
                client_batch_id=client_batch_id,
            )
        response_payload = dict(uploaded)
        response_payload["task_id"] = setup.task.task_id
        response_payload["knowledge_attachment"] = knowledge_summary
        return create_json_response_with_task_id(
            response_payload,
            setup.task.task_id,
            status_code=202,
        )
    except asyncio.CancelledError:
        try:
            await cancel(setup.registry, setup.task.task_id, reason="Client disconnected.")
        except RECOVERABLE_EXCEPTIONS as cancel_error:
            log_handled_exception(
                setup.logger,
                cancel_error,
                message="Failed to cancel RAG upload task after request disconnect.",
                operation=OPERATION_WEBUI_UPLOAD_RAG_DOCUMENT_CANCEL_AFTER_DISCONNECT,
                details={"task_id": setup.task.task_id},
                level="warning",
            )
        if knowledge_summary is not None:
            try:
                await finalize_knowledge_attachment_task_failure(
                    api_context=api_context,
                    task_id=setup.task.task_id,
                    processing_state="cancelled",
                    terminal_item_status="cancelled",
                    error_message="Client disconnected.",
                )
            except RECOVERABLE_EXCEPTIONS as finalize_error:
                log_handled_exception(
                    setup.logger,
                    finalize_error,
                    message="Failed to finalize RAG upload knowledge attachment after disconnect.",
                    operation=OPERATION_WEBUI_UPLOAD_RAG_DOCUMENT_CANCEL_AFTER_DISCONNECT,
                    details={"task_id": setup.task.task_id},
                    level="warning",
                )
        raise
    except HANDLED_RAG_DOCUMENT_UPLOAD_EXCEPTIONS as exception:
        if not isinstance(exception, TaskCancelledError):
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_WEBUI_UPLOAD_RAG_DOCUMENT,
            )
            log_exception(
                setup.logger,
                coerced,
                message="RAG document upload failed.",
                operation=OPERATION_WEBUI_UPLOAD_RAG_DOCUMENT,
                trace_id=get_context_trace_id(setup.context),
                details={
                    "conv_id": setup.resolved_id,
                    "filename": setup.reservation_tracker.current_filename,
                    "task_id": setup.task.task_id,
                },
            )
        if knowledge_summary is not None and not isinstance(exception, TaskCancelledError):
            await finalize_knowledge_attachment_task_failure(
                api_context=api_context,
                task_id=setup.task.task_id,
                processing_state="error",
                terminal_item_status="error",
                error_message=str(exception),
            )
        await handle_rag_document_upload_exception(
            request,
            exception=exception,
            registry=setup.registry,
            task_id=setup.task.task_id,
            context=setup.context,
            logger=setup.logger,
            resolved_id=setup.resolved_id,
            filename=setup.reservation_tracker.current_filename,
        )
    finally:
        await finalize_rag_upload_cleanup(
            logger=setup.logger,
            bridge=setup.bridge,
            content_size=content_size,
            task_id=setup.task.task_id,
            temp_file_path=temp_file_path,
        )
