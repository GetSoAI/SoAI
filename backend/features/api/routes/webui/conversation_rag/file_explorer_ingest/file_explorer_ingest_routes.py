"""SoAI - WebUI per-conversation File Explorer to RAG ingestion routes [backend/features/api/routes/webui/conversation_rag/file_explorer_ingest/file_explorer_ingest_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request, status
from fastapi.responses import JSONResponse

from core.database.requests import UpdateRAGConfigRequest, UpdateRAGConfigWithDefaultsRequest
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.rag.conversation_config import read_rag_enabled_from_config
from core.state.access import AccessAction
from core.tasks.asyncio_task_spawner import create_tracked_task
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.type_catalog import TASK_TYPE_BACKGROUND_JOB
from features.api.routes.file_explorer.route_scope_context import (
    require_file_explorer_core_scoped,
)
from features.api.routes.webui.conversation_rag.file_explorer_ingest.job_runner import (
    run_rag_file_explorer_ingest_job,
)
from features.api.routes.webui.conversation_rag.ingest_preflight import (
    resolve_conversation_rag_ingest_preflight,
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
from features.api.routes.webui.request_validators import require_user_id
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    get_request_trace_id,
    raise_api_error,
    resolve_api_context,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_server_error
from features.api.runtime.request_cancellation import (
    resolve_request_cancellation_id_or_create,
)
from features.api.schemas.rag import RAGFileExplorerIngestRequest
from features.file_explorer.path_resolution import canonicalize_virtual_path

if TYPE_CHECKING:
    from core.tasks.protocols_query import TaskRegistryQueryView

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.file_explorer_ingest_routes"
LOGGER_NAME_JOB_TASK = "SoAI.features.api.file_explorer_ingest_job_task"
OPERATION_READ_PATH_METADATA = "webui.conversation_rag.file_explorer_ingest.read_path_metadata"
OPERATION_START_JOB = "webui.conversation_rag.file_explorer_ingest.start_job"


async def _has_active_file_explorer_ingest_task(
    registry: TaskRegistryQueryView,
    *,
    resolved_conv_id: str,
) -> bool:
    tasks = await registry.query_active_filtered(
        owner_type="conversation",
        owner_id=resolved_conv_id,
        limit=20,
    )
    for task in tasks:
        operation_value = task.metadata.get("operation")
        if isinstance(operation_value, str) and operation_value == "rag_file_explorer_ingest":
            return True
    return False


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/{conv_id}/rag/ingest-file-explorer",
        status_code=202,
        dependencies=require_action_dependencies(
            AccessAction.RAG_USE,
            AccessAction.FILE_EXPLORER_READ,
        ),
    )
    async def ingest_file_explorer_folder(
        request: Request,
        conv_id: str,
        payload: RAGFileExplorerIngestRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        logger = get_logger(LOGGER_NAME)
        user_id = require_user_id(request, current_user)
        _, resolved_conv_id = await resolve_conversation_rag_ingest_preflight(
            request=request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=user_id,
            reindex_error_verb="import files",
        )
        async with api_context.dependencies.conversation_rag_ingest_locks.lock(resolved_conv_id):
            if await _has_active_file_explorer_ingest_task(
                api_context.dependencies.task_registry_queries,
                resolved_conv_id=resolved_conv_id,
            ):
                raise_api_error(
                    request,
                    409,
                    "conflict",
                    "A File Explorer import is already running for this conversation.",
                )
            scoped = require_file_explorer_core_scoped(
                request,
                api_context=api_context,
                current_user=current_user,
            )
            canonical_path = canonicalize_virtual_path(scoped.root_scope, payload.path)
            try:
                metadata = await scoped.file_explorer_core.get_metadata(
                    scoped.root_scope,
                    canonical_path,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to read File Explorer metadata for ingestion path.",
                    operation=OPERATION_READ_PATH_METADATA,
                    details={"path": canonical_path, "conv_id": resolved_conv_id},
                )
                raise_server_error(request, "Failed to read File Explorer path metadata.")
            if not metadata.is_directory:
                raise_api_error(
                    request,
                    400,
                    "validation_error",
                    "Ingest path must be a directory.",
                )
            async with api_context.dependencies.conversation_agent_settings_locks.lock(
                (user_id, resolved_conv_id),
            ):
                rag_config = await api_context.dependencies.database_files.get_rag_config(
                    resolved_conv_id
                )
                if rag_config is not None and not read_rag_enabled_from_config(rag_config):
                    await api_context.dependencies.database_files.update_rag_config_with_defaults(
                        UpdateRAGConfigWithDefaultsRequest(
                            update=UpdateRAGConfigRequest(
                                conv_id=resolved_conv_id,
                                enabled=True,
                            ),
                            user_id=user_id,
                        )
                    )
            registry = api_context.dependencies.task_registry
            cancellation_id = resolve_request_cancellation_id_or_create(
                request,
                subsystem="rag",
                trace_id=get_request_trace_id(request),
                owner=resolved_conv_id,
            )
            task = await create(
                registry,
                task_type=TASK_TYPE_BACKGROUND_JOB,
                user_id=user_id,
                owner_id=resolved_conv_id,
                owner_type="conversation",
                cancellation_id=cancellation_id,
                status=TaskStatus.WORKING,
                progress_total=100,
                status_message="Importing from File Explorer",
                metadata={
                    "operation": "rag_file_explorer_ingest",
                    "conv_id": resolved_conv_id,
                    "path": canonical_path,
                },
            )
            knowledge_summary = await ensure_and_publish_knowledge_attachment(
                api_context=api_context,
                conv_id=resolved_conv_id,
                user_id=user_id,
                source_type="file_explorer_folder_import",
                operation_type="added",
                title=canonical_path,
                root_label=canonical_path,
                root_virtual_path=canonical_path,
                task_id=task.task_id,
                client_batch_id=payload.client_batch_id,
            )
        try:
            job_task = await create_tracked_task(
                run_rag_file_explorer_ingest_job(
                    request=request,
                    api_context=api_context,
                    task=task,
                    resolved_conv_id=resolved_conv_id,
                    user_id=user_id,
                    workspace_path=scoped.root_scope.root_path,
                    root_virtual_path=canonical_path,
                    recursive=bool(payload.recursive),
                    knowledge_attachment_id=require_knowledge_attachment_id(knowledge_summary),
                    client_batch_id=payload.client_batch_id,
                ),
                name=f"rag-file-explorer-ingest:{task.task_id}",
                logger=get_logger(LOGGER_NAME_JOB_TASK),
                cancellation_binder=api_context.dependencies.task_cancellation_binder,
                cancellation_id=task.cancellation_id,
                owner="rag_file_explorer_ingest",
                metadata={"task_id": task.task_id, "conv_id": resolved_conv_id},
            )
            api_context.dependencies.task_finalizer_tracker.track_finalizer(job_task)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to start RAG File Explorer ingest job.",
                operation=OPERATION_START_JOB,
                details={"task_id": task.task_id, "conv_id": resolved_conv_id},
            )
            await finalize(
                api_context.dependencies.task_registry,
                task.task_id,
                TaskStatus.FAILED,
                error_message="Import failed to start.",
            )
            await finalize_knowledge_attachment_task_failure(
                api_context=api_context,
                task_id=task.task_id,
                processing_state="error",
                terminal_item_status="error",
                error_message="Import failed to start.",
            )
            raise_server_error(request, "Failed to start File Explorer import.")
        return JSONResponse(
            content={
                "status": "queued",
                "task_id": task.task_id,
                "conv_id": resolved_conv_id,
                "knowledge_attachment_id": require_knowledge_attachment_id(knowledge_summary),
                "knowledge_attachment": knowledge_summary,
            },
            status_code=status.HTTP_202_ACCEPTED,
        )
