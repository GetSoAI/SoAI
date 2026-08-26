"""SoAI - WebUI per-conversation RAG document batch upload routes [backend/features/api/routes/webui/conversation_rag/documents/batch_upload/batch_upload_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.attachments.attachment_content_validation import require_knowledge_source_type
from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.errors.exception_logging import log_exception
from core.errors.exceptions import PayloadTooLargeError, RateLimitError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.upload_policy import resolve_temp_directory_runtime
from core.logging.trace import get_logger
from core.state.access import AccessAction
from core.tasks.cancellation_token_scope import cancellation_token_scope
from features.api.routes.upload_streaming_multipart_staged_uploads import (
    stage_batch_relative_paths_sizes_upload,
)
from features.api.routes.webui.conversation_rag.documents.batch_upload.failure_finalization import (
    finalize_batch_upload_failure,
)
from features.api.routes.webui.conversation_rag.documents.batch_upload.processing import (
    process_staged_batch_upload,
)
from features.api.routes.webui.conversation_rag.documents.batch_upload.staging import (
    build_batch_upload_reservation_tracker,
    cleanup_batch_upload_staged_parts,
    create_batch_upload_declared_total_reporter,
    resolve_batch_upload_cancellation_id,
)
from features.api.routes.webui.conversation_rag.documents.batch_upload.state import (
    RagBatchKnowledgeState,
    RagBatchUploadMultipartState,
)
from features.api.routes.webui.conversation_rag.ingest_preflight import (
    resolve_conversation_rag_ingest_preflight,
)
from features.api.routes.webui.request_validators import require_user_id
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    raise_api_error,
    resolve_api_context,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_server_error
from features.api.runtime.upload_error_resolution import resolve_upload_api_error

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingStagedPart,
    )

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.batch_upload_routes"
LOGGER_NAME_STREAMING_MULTIPART = "SoAI.features.api.upload_streaming_multipart"
OPERATION = "webui.conversation_rag.upload_documents_batch"


async def upload_rag_documents_batch(
    request: Request,
    conv_id: str,
    include_results: bool = Query(default=True),
    client_batch_id: str | None = Query(None),
    attachment_source: str = Query("composer_folder_upload"),
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    logger = get_logger(LOGGER_NAME)
    user_id = require_user_id(request, current_user)
    resolved_attachment_source = require_knowledge_source_type(attachment_source)
    rag_engine, resolved_id = await resolve_conversation_rag_ingest_preflight(
        request=request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
        reindex_error_verb="upload documents",
    )
    max_upload_bytes = resolve_upload_limit_bytes(
        api_context.dependencies.config,
        UploadLimitType.FILE,
    )
    try:
        temp_dir = resolve_temp_directory_runtime(api_context.dependencies.config)
    except ValidationError as exception:
        raise_server_error(request, str(exception))
    state = RagBatchUploadMultipartState()
    results: list[JSONDict] = []
    staged_files: list[StreamingStagedPart] = []
    relative_paths: list[str] = []
    knowledge_state = RagBatchKnowledgeState()
    status_payload: JSONDict = {
        "status": "accepted",
        "conv_id": resolved_id,
        "queued": 0,
        "rate_limited": 0,
        "failed": 0,
        "total": 0,
    }
    if include_results:
        status_payload["results"] = results
    reservation_tracker = build_batch_upload_reservation_tracker(
        storage_manager=api_context.dependencies.storage_manager,
        temp_dir=temp_dir,
        resolved_conv_id=resolved_id,
    )

    try:
        cancellation_id = resolve_batch_upload_cancellation_id(request)
        async with cancellation_token_scope(
            api_context.dependencies.token_collection,
            api_context.dependencies.cancellation_history,
            api_context.dependencies.cancellation_event_bus,
            cancellation_id=cancellation_id,
            owner="rag_document_batch_upload",
            metadata={"conv_id": resolved_id},
        ) as token:
            staged_upload = await stage_batch_relative_paths_sizes_upload(
                request,
                parser_semaphore=api_context.dependencies.multipart_parser_semaphore,
                temp_dir=temp_dir,
                max_upload_bytes=max_upload_bytes,
                token=token,
                report_bytes=state.report_bytes,
                report_file_start=state.report_file_start,
                report_stream_bytes=state.report_stream_bytes,
                allow_null_sizes=True,
                allow_number_sizes=True,
                on_declared_total=create_batch_upload_declared_total_reporter(
                    reservation_tracker=reservation_tracker,
                ),
                write_controller=reservation_tracker,
                logger=get_logger(LOGGER_NAME_STREAMING_MULTIPART),
            )
            parsed_result = staged_upload.parsed
            staged_files = list(parsed_result.files)
            relative_paths = list(staged_upload.relative_paths)
            queued, rate_limited, failed = await process_staged_batch_upload(
                token=token,
                api_context=api_context,
                rag_engine=rag_engine,
                resolved_conv_id=resolved_id,
                user_id=user_id,
                staged_upload=staged_upload,
                include_results=include_results,
                results=results,
                logger=logger,
                batch_state=state,
                knowledge_state=knowledge_state,
                attachment_source=resolved_attachment_source,
                client_batch_id=client_batch_id,
            )
            staged_files = []
            status_payload["queued"] = int(queued)
            status_payload["rate_limited"] = int(rate_limited)
            status_payload["failed"] = int(failed)
            status_payload["total"] = len(parsed_result.files)
            if knowledge_state.latest_summary is not None:
                status_payload["knowledge_attachment"] = knowledge_state.latest_summary
            return JSONResponse(content=status_payload, status_code=202)
    except TaskCancelledError:
        knowledge_state.latest_summary = await finalize_batch_upload_failure(
            api_context=api_context,
            conv_id=resolved_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_state.knowledge_attachment_id,
            files=staged_files,
            relative_paths=relative_paths,
            state=state,
            processing_state="cancelled",
            terminal_item_status="cancelled",
            error_message="RAG document batch upload was cancelled.",
        )
        raise_api_error(
            request,
            499,
            "cancelled",
            "RAG document batch upload was cancelled.",
        )
    except (PayloadTooLargeError, RateLimitError, ValidationError) as exception:
        knowledge_state.latest_summary = await finalize_batch_upload_failure(
            api_context=api_context,
            conv_id=resolved_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_state.knowledge_attachment_id,
            files=staged_files,
            relative_paths=relative_paths,
            state=state,
            processing_state="error",
            terminal_item_status="error",
            error_message=str(exception),
        )
        http_status, code, message, _, headers = resolve_upload_api_error(
            exception,
            default_server_message="Failed to upload RAG document.",
        )
        raise_api_error(
            request,
            http_status,
            code,
            message,
            headers=dict(headers) if headers else None,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        knowledge_state.latest_summary = await finalize_batch_upload_failure(
            api_context=api_context,
            conv_id=resolved_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_state.knowledge_attachment_id,
            files=staged_files,
            relative_paths=relative_paths,
            state=state,
            processing_state="error",
            terminal_item_status="error",
            error_message=str(exception),
        )
        log_exception(
            logger,
            exception,
            message="Failed to upload RAG documents batch",
            operation=OPERATION,
            details={
                "conv_id": resolved_id,
                "bytes_done": state.bytes_done,
                "stream_bytes_done": state.stream_bytes_done,
                "declared_total_bytes": reservation_tracker.declared_size,
                "last_filename": state.last_filename,
                "file_counter": state.file_counter,
            },
        )
        raise_server_error(request, "Failed to upload RAG documents batch.")
    finally:
        reservation_tracker.release_active_reservation()
        if staged_files:
            await uncancel_then_cleanup(
                cleanup_batch_upload_staged_parts(
                    files=staged_files,
                    logger=logger,
                    resolved_conv_id=resolved_id,
                ),
            )


def register_endpoints(router: APIRouter) -> None:
    router.post(
        "/conversations/{conv_id}/rag/documents/batch",
        status_code=202,
        dependencies=require_action_dependencies(AccessAction.RAG_USE),
    )(upload_rag_documents_batch)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.webui)
