"""SoAI - WebUI conversation attachment content response helpers [backend/features/api/routes/webui/conversation_attachments/content_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from starlette.responses import Response, StreamingResponse

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.files.managed_file_opening import ManagedFileDescriptor, open_managed_file_descriptor
from features.api.routes.webui.descriptor_content_response import (
    open_descriptor_streaming_response,
    open_descriptor_thumbnail_response,
)

__all__ = ("open_attachment_streaming_response", "open_attachment_thumbnail_response")


def _close_managed_file_descriptor(managed: ManagedFileDescriptor) -> None:
    os.close(managed.descriptor)


def _render_thumbnail_response(managed: ManagedFileDescriptor, filename: str) -> Response:
    return open_descriptor_thumbnail_response(
        descriptor=managed.descriptor,
        filename=filename,
    )


async def open_attachment_streaming_response(
    *,
    storage_root: str,
    file_path: str,
    filename: str,
    mime_type: str,
    download: bool,
) -> StreamingResponse:
    managed = await run_joined_thread_call(
        open_managed_file_descriptor,
        storage_root,
        file_path,
        task_name="webui-attachment-content-open",
        cancelled_result_cleanup=_close_managed_file_descriptor,
    )
    return open_descriptor_streaming_response(
        descriptor=managed.descriptor,
        size_bytes=managed.size_bytes,
        filename=filename,
        mime_type=mime_type,
        download=download,
    )


async def open_attachment_thumbnail_response(
    *,
    storage_root: str,
    file_path: str,
    filename: str,
) -> Response:
    managed = await run_joined_thread_call(
        open_managed_file_descriptor,
        storage_root,
        file_path,
        task_name="webui-attachment-thumbnail-open",
        cancelled_result_cleanup=_close_managed_file_descriptor,
    )
    return await run_joined_thread_call(
        _render_thumbnail_response,
        managed,
        filename,
        task_name="webui-attachment-thumbnail-render",
    )
