"""SoAI - WebUI conversation attachment content response helpers [backend/features/api/routes/webui/conversation_attachments/content_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from starlette.responses import Response, StreamingResponse

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from features.api.routes.webui.descriptor_content_response import (
    open_descriptor_streaming_response,
    open_descriptor_thumbnail_response,
)

if TYPE_CHECKING:
    from core.files.managed_file_opening import ManagedFileDescriptor

__all__ = ("open_attachment_streaming_response", "open_attachment_thumbnail_response")

LOGGER_NAME = "SoAI.features.api.content_response"
OPERATION_WEBUI_ATTACHMENT_CONTENT_RESPONSE = "webui.conversation_attachments.content_response"


def _render_thumbnail_response(managed: ManagedFileDescriptor, filename: str) -> Response:
    return open_descriptor_thumbnail_response(
        descriptor=managed.descriptor,
        filename=filename,
    )


async def open_attachment_streaming_response(
    *,
    managed: ManagedFileDescriptor,
    filename: str,
    mime_type: str,
    download: bool,
) -> StreamingResponse:
    try:
        return open_descriptor_streaming_response(
            descriptor=managed.descriptor,
            size_bytes=managed.size_bytes,
            filename=filename,
            mime_type=mime_type,
            download=download,
        )
    except asyncio.CancelledError:
        os.close(managed.descriptor)
        raise
    except Exception as exception:
        os.close(managed.descriptor)
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_WEBUI_ATTACHMENT_CONTENT_RESPONSE,
        )
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to construct WebUI attachment streaming response.",
            operation=OPERATION_WEBUI_ATTACHMENT_CONTENT_RESPONSE,
        )
        raise


async def open_attachment_thumbnail_response(
    *,
    managed: ManagedFileDescriptor,
    filename: str,
) -> Response:
    return await run_joined_thread_call(
        _render_thumbnail_response,
        managed,
        filename,
        task_name="webui-attachment-thumbnail-render",
    )
