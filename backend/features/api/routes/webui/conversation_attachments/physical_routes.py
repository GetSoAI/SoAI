"""SoAI - WebUI physical conversation attachment routes [backend/features/api/routes/webui/conversation_attachments/physical_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request, status
from starlette.responses import JSONResponse, Response

from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.operations import remove_if_exists
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from features.api.routes.webui.conversation_attachments.payloads import (
    serialize_physical_attachment,
)
from features.api.routes.webui.conversation_attachments.physical_file_routes import (
    register_physical_attachment_file_routes,
)
from features.api.routes.webui.conversation_attachments.physical_route_support import (
    PHYSICAL_ATTACHMENT_ROUTE_EXCEPTIONS,
    raise_physical_attachment_route_error,
    require_physical_attachment_access,
)
from features.api.routes.webui.conversation_attachments.physical_upload_staging import (
    stage_physical_attachment_upload,
)
from features.api.routes.webui.conversation_attachments.request_validation import (
    require_attachment_request_id,
    require_attachment_source,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.chat.direct_attachment_ingestion import (
    DirectAttachmentIngestionDependencies,
    ingest_staged_direct_attachment,
)
from features.chat.direct_attachment_parsing import (
    DirectAttachmentParseDependencies,
    parse_direct_attachment,
)

__all__ = ("register_physical_attachment_routes",)

LOGGER_NAME = "SoAI.features.api.physical_routes"
OPERATION_SCHEDULE_PARSE = "webui.conversation_attachments.schedule_parse"


def register_physical_attachment_routes(routers: ApiRouters) -> None:
    @routers.webui.post("/conversations/{conv_id}/attachments", status_code=status.HTTP_201_CREATED)
    async def stage_attachment(
        request: Request,
        conv_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            conversation_context = await require_conversation_access_context(
                request,
                api_context=api_context,
                conv_id=conv_id,
                user_id=current_user["id"],
            )
            upload = await stage_physical_attachment_upload(
                request,
                api_context=api_context,
            )
            try:
                _ = require_attachment_request_id(upload.client_request_id)
                _ = require_attachment_source(upload.source)
                ingestion = await ingest_staged_direct_attachment(
                    deps=DirectAttachmentIngestionDependencies(
                        config=api_context.dependencies.config,
                        files=api_context.dependencies.files,
                        database_attachments=(
                            api_context.dependencies.database_conversation_attachments
                        ),
                        storage_manager=api_context.dependencies.storage_manager,
                        token_collection=api_context.dependencies.token_collection,
                        cancellation_history=api_context.dependencies.cancellation_history,
                        cancellation_event_bus=api_context.dependencies.cancellation_event_bus,
                    ),
                    staged_path=upload.part.temp_path,
                    staged_size=upload.part.size_bytes,
                    staged_sha256=upload.part.content_sha256,
                    declared_content_type=upload.part.content_type,
                    display_name=upload.display_name,
                    source_filename=upload.part.original_filename,
                    conv_id=conversation_context.resolved_conv_id,
                    user_id=current_user["id"],
                    client_attachment_id=upload.client_attachment_id,
                    cancellation_id=upload.cancellation_id,
                )
            finally:
                remove_if_exists(upload.part.temp_path)
            staged = ingestion.attachment
            if not ingestion.created:
                return JSONResponse(content=serialize_physical_attachment(staged))
            if staged.get("parse_state") != "pending":
                return JSONResponse(content=serialize_physical_attachment(staged))
            parse_dependencies = DirectAttachmentParseDependencies(
                config=api_context.dependencies.config,
                files=api_context.dependencies.files,
                database_files=api_context.dependencies.database_files,
                database_attachments=api_context.dependencies.database_conversation_attachments,
                document_reader=api_context.dependencies.document_reader,
                parser_registry_factory=api_context.dependencies.parser_registry_factory,
                event_bus=api_context.dependencies.event_bus,
            )

            async def parse_staged_attachment() -> None:
                _ = await parse_direct_attachment(
                    deps=parse_dependencies,
                    attachment=staged,
                )

            try:
                _ = await api_context.dependencies.attachment_parse_tasks.schedule(
                    str(staged["attachment_id"]),
                    parse_staged_attachment,
                )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                log_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="Failed to schedule attachment parse worker.",
                    operation=OPERATION_SCHEDULE_PARSE,
                    details={"attachment_id": staged.get("attachment_id")},
                )
                failed = await api_context.dependencies.database_conversation_attachments.update_attachment_parse_state(
                    conv_id=str(staged["conv_id"]),
                    user_id=current_user["id"],
                    attachment_id=str(staged["attachment_id"]),
                    provider_mode=None,
                    provider_text=None,
                    provider_text_truncated=None,
                    parse_state="failed",
                    parse_error="Attachment parsing could not be scheduled.",
                    parsed_at_ms=None,
                    updated_at_ms=epoch_ms(),
                )
                if failed is not None:
                    staged = failed
            return JSONResponse(
                content=serialize_physical_attachment(staged),
                status_code=status.HTTP_201_CREATED,
            )
        except PHYSICAL_ATTACHMENT_ROUTE_EXCEPTIONS as exception:
            raise_physical_attachment_route_error(
                request,
                exception,
                logger=get_logger(LOGGER_NAME),
            )

    @routers.webui.get("/conversations/{conv_id}/attachments/{attachment_id}")
    async def get_attachment(
        request: Request,
        conv_id: str,
        attachment_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        access = await require_physical_attachment_access(
            request,
            api_context=api_context,
            conv_id=conv_id,
            attachment_id=attachment_id,
            user_id=current_user["id"],
        )
        return JSONResponse(content=serialize_physical_attachment(access.attachment))

    register_physical_attachment_file_routes(routers)
