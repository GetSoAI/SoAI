"""SoAI - WebUI physical attachment route support [backend/features/api/routes/webui/conversation_attachments/physical_route_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    ConflictError,
    InsufficientDiskSpaceError,
    PayloadTooLargeError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.managed_storage_errors import FileStorageSecurityError
from core.validation.integers import is_strict_int
from features.api.routes.webui.conversation_attachments.route_errors import (
    raise_attachment_route_error,
)
from features.api.runtime.context import get_request_trace_id
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.errors import raise_not_found

if TYPE_CHECKING:
    from fastapi import Request

    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.runtime.conversation_access import ConversationAccessContext

__all__ = (
    "PHYSICAL_ATTACHMENT_ROUTE_EXCEPTIONS",
    "PhysicalAttachmentAccess",
    "raise_physical_attachment_route_error",
    "require_physical_attachment_access",
)

OPERATION_WEBUI_PHYSICAL_ATTACHMENT_ROUTE = "webui.conversation_attachments.physical_route"
PHYSICAL_ATTACHMENT_ROUTE_ERROR_MESSAGE = "Conversation physical attachment route failed."
PHYSICAL_ATTACHMENT_ROUTE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ConflictError,
    InsufficientDiskSpaceError,
    PayloadTooLargeError,
    ValidationError,
    FileStorageSecurityError,
    *RECOVERABLE_EXCEPTIONS,
)


@dataclass(frozen=True, slots=True)
class PhysicalAttachmentAccess:
    conversation: ConversationAccessContext
    attachment: JSONDict


async def require_physical_attachment_access(
    request: Request,
    *,
    api_context: ApiContext,
    conv_id: str,
    attachment_id: str,
    user_id: int,
) -> PhysicalAttachmentAccess:
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
    )
    attachment = await api_context.dependencies.database_conversation_attachments.get_attachment(
        conv_id=conversation_context.resolved_conv_id,
        user_id=user_id,
        attachment_id=attachment_id,
    )
    if attachment is None:
        raise_not_found(request, "Attachment not found.")
    if (
        attachment.get("attachment_id") != attachment_id
        or attachment.get("conv_id") != conversation_context.resolved_conv_id
        or not is_strict_int(attachment.get("user_id"))
        or attachment.get("user_id") != user_id
    ):
        raise ValidationError("Attachment access identity is invalid.")
    return PhysicalAttachmentAccess(
        conversation=conversation_context,
        attachment=attachment,
    )


def raise_physical_attachment_route_error(
    request: Request,
    exception: Exception,
    *,
    logger: LoggerProtocol,
) -> NoReturn:
    if isinstance(
        exception,
        ConflictError
        | InsufficientDiskSpaceError
        | PayloadTooLargeError
        | ValidationError
        | FileStorageSecurityError,
    ):
        raise_attachment_route_error(request, exception)
    log_exception(
        logger,
        exception,
        message=PHYSICAL_ATTACHMENT_ROUTE_ERROR_MESSAGE,
        operation=OPERATION_WEBUI_PHYSICAL_ATTACHMENT_ROUTE,
        trace_id=get_request_trace_id(request),
    )
    raise_attachment_route_error(request, exception, already_logged=True)
