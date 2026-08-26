"""SoAI - WebUI physical attachment file routes [backend/features/api/routes/webui/conversation_attachments/physical_file_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Query, Request
from starlette.responses import Response

from core.errors.exceptions import ValidationError
from core.files.managed_file_deletion import delete_managed_file
from core.files.storage_root_resolution import resolve_managed_files_storage_root
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from features.api.routes.webui.conversation_attachments.content_response import (
    open_attachment_streaming_response,
    open_attachment_thumbnail_response,
)
from features.api.routes.webui.conversation_attachments.file_catalog_access import (
    get_attachment_file_catalog_record,
)
from features.api.routes.webui.conversation_attachments.physical_route_support import (
    PHYSICAL_ATTACHMENT_ROUTE_EXCEPTIONS,
    raise_physical_attachment_route_error,
    require_physical_attachment_access,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    resolve_api_context,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_not_found

__all__ = ("register_physical_attachment_file_routes",)

LOGGER_NAME = "SoAI.features.api.physical_file_routes"


def register_physical_attachment_file_routes(routers: ApiRouters) -> None:
    @routers.webui.get("/conversations/{conv_id}/attachments/{attachment_id}/content")
    async def get_attachment_content(
        request: Request,
        conv_id: str,
        attachment_id: str,
        download: int = Query(0, ge=0, le=1),
        thumbnail: int = Query(0, ge=0, le=1),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            access = await require_physical_attachment_access(
                request,
                api_context=api_context,
                conv_id=conv_id,
                attachment_id=attachment_id,
                user_id=current_user["id"],
            )
            attachment = access.attachment
            file_record = await get_attachment_file_catalog_record(
                database_files=api_context.dependencies.database_files,
                attachment=attachment,
                user_id=current_user["id"],
            )
            storage_root = resolve_managed_files_storage_root(
                api_context.dependencies.config,
                api_context.dependencies.files,
            )
            if thumbnail == 1 and download == 0:
                if str(attachment["preview_type"]) != "image":
                    raise ValidationError("Attachment thumbnail requires an image attachment.")
                return await open_attachment_thumbnail_response(
                    storage_root=storage_root,
                    file_path=file_record["file_path"],
                    filename=str(attachment["filename"]),
                )
            return await open_attachment_streaming_response(
                storage_root=storage_root,
                file_path=file_record["file_path"],
                filename=str(attachment["filename"]),
                mime_type=str(attachment["mime_type"]),
                download=download == 1,
            )
        except PHYSICAL_ATTACHMENT_ROUTE_EXCEPTIONS as exception:
            raise_physical_attachment_route_error(
                request,
                exception,
                logger=get_logger(LOGGER_NAME),
            )

    @routers.webui.delete("/conversations/{conv_id}/attachments/{attachment_id}", status_code=204)
    async def delete_attachment(
        request: Request,
        conv_id: str,
        attachment_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            access = await require_physical_attachment_access(
                request,
                api_context=api_context,
                conv_id=conv_id,
                attachment_id=attachment_id,
                user_id=current_user["id"],
            )
            attachment = access.attachment
            deletion_mark = await api_context.dependencies.database_conversation_attachments.mark_unbound_attachment_unused(
                conv_id=access.conversation.resolved_conv_id,
                user_id=current_user["id"],
                attachment_id=attachment_id,
                updated_at_ms=epoch_ms(),
            )
            if deletion_mark is None:
                raise_not_found(request, "Attachment not found.")
            await api_context.dependencies.attachment_parse_tasks.cancel_and_wait(attachment_id)
            deletion_plan = await api_context.dependencies.database_conversation_attachments.prepare_unbound_attachment_deletion(
                conv_id=access.conversation.resolved_conv_id,
                user_id=current_user["id"],
                attachment_id=attachment_id,
            )
            if deletion_plan is None:
                return Response(status_code=204)
            if not deletion_plan.requires_file_deletion:
                return Response(status_code=204)
            file_record = await get_attachment_file_catalog_record(
                database_files=api_context.dependencies.database_files,
                attachment=attachment,
                user_id=current_user["id"],
            )
            storage_root = resolve_managed_files_storage_root(
                api_context.dependencies.config,
                api_context.dependencies.files,
            )
            await delete_managed_file(
                storage_root,
                file_record["file_path"],
            )
            await api_context.dependencies.database_conversation_attachments.finalize_unbound_attachment_deletion(
                conv_id=access.conversation.resolved_conv_id,
                user_id=current_user["id"],
                attachment_id=attachment_id,
            )
            return Response(status_code=204)
        except PHYSICAL_ATTACHMENT_ROUTE_EXCEPTIONS as exception:
            raise_physical_attachment_route_error(
                request,
                exception,
                logger=get_logger(LOGGER_NAME),
            )
