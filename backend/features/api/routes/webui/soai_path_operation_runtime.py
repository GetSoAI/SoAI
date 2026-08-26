"""SoAI - Conversation SoAI path operation execution [backend/features/api/routes/webui/soai_path_operation_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Iterator

from fastapi import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import SecurityError, ValidationError
from core.files.workspace_descriptor import (
    WorkspaceFileDescriptor,
    open_workspace_file_descriptor,
)
from core.files.workspace_listing import list_workspace_directory
from features.api.routes.webui.soai_path_operation_resolution import (
    ResolvedSoaiPath,
    SoaiPathRouteTarget,
    resolve_soai_path_route_target,
    unavailable_soai_path_response,
)
from features.api.routes.webui.soai_path_operation_validation import (
    SoaiPathOperationRequest,
    no_store_headers,
    source_reference_value,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.current_user import CurrentUser

__all__ = (
    "SoaiPathOperationRequest",
    "download_soai_path_response",
    "preview_soai_path_response",
    "read_soai_path_response",
)


def _stream_descriptor(descriptor: int) -> Iterator[bytes]:
    try:
        while True:
            chunk = os.read(descriptor, MIB_BYTES)
            if not chunk:
                break
            yield chunk
    finally:
        os.close(descriptor)


async def preview_soai_path_response(
    *,
    request: Request,
    conv_id: str,
    body: SoaiPathOperationRequest,
    current_user: CurrentUser,
    api_context: ApiContext,
) -> JSONResponse:
    target = SoaiPathRouteTarget(request, conv_id, body, current_user, api_context)
    resolved = await resolve_soai_path_route_target(
        target,
    )
    if isinstance(resolved, JSONResponse):
        return resolved
    if resolved.canonical.get("entry_type") != "folder":
        return JSONResponse(
            content={"state": "available", "content_part": resolved.canonical},
            headers=no_store_headers(),
        )
    try:
        entries = list_workspace_directory(
            resolved.scope.effective_root_real,
            source_reference_value(resolved.canonical),
            error_cls=ValidationError,
        )
    except (OSError, SecurityError, ValidationError):
        return unavailable_soai_path_response()
    folder_max_entries = api_context.dependencies.config.get_int(
        "SERVER.WEBUI.SOAI_LINKS.PROJECTION_FOLDER_MAX_ENTRIES",
    )
    return JSONResponse(
        content={
            "state": "available",
            "content_part": resolved.canonical,
            "entries": [
                {
                    "name": entry.name,
                    "entry_type": entry.entry_type,
                    "size_bytes": entry.size_bytes,
                    "modified_at_ms": entry.modified_at_ms,
                }
                for entry in entries[:folder_max_entries]
            ],
        },
        headers=no_store_headers(),
    )


async def read_soai_path_response(
    *,
    request: Request,
    conv_id: str,
    body: SoaiPathOperationRequest,
    current_user: CurrentUser,
    api_context: ApiContext,
) -> JSONResponse:
    target = SoaiPathRouteTarget(request, conv_id, body, current_user, api_context)
    file_target = await _open_file_soai_path_target(
        target,
        file_error_message="SoAI path read requires a file target.",
    )
    if isinstance(file_target, JSONResponse):
        return file_target
    resolved, opened = file_target
    try:
        try:
            text = os.read(opened.descriptor, min(opened.size_bytes, 262144)).decode(
                "utf-8",
                errors="replace",
            )
        except OSError:
            return unavailable_soai_path_response()
    finally:
        os.close(opened.descriptor)
    return JSONResponse(
        content={"state": "available", "content_part": resolved.canonical, "text": text},
        headers=no_store_headers(),
    )


async def download_soai_path_response(
    *,
    request: Request,
    conv_id: str,
    body: SoaiPathOperationRequest,
    current_user: CurrentUser,
    api_context: ApiContext,
) -> Response:
    target = SoaiPathRouteTarget(request, conv_id, body, current_user, api_context)
    file_target = await _open_file_soai_path_target(
        target,
        file_error_message="SoAI path download requires a file target.",
    )
    if isinstance(file_target, JSONResponse):
        return file_target
    _, opened = file_target
    headers = no_store_headers()
    headers["Content-Disposition"] = 'attachment; filename="soai-path-download"'
    return StreamingResponse(_stream_descriptor(opened.descriptor), headers=headers)


async def _open_file_soai_path_target(
    target: SoaiPathRouteTarget,
    *,
    file_error_message: str,
) -> tuple[ResolvedSoaiPath, WorkspaceFileDescriptor] | JSONResponse:
    resolved = await resolve_soai_path_route_target(target)
    if isinstance(resolved, JSONResponse):
        return resolved
    if resolved.canonical.get("entry_type") != "file":
        raise ValidationError(file_error_message)
    try:
        opened = open_workspace_file_descriptor(
            resolved.scope.effective_root_real,
            source_reference_value(resolved.canonical),
            error_cls=ValidationError,
        )
    except (OSError, SecurityError, ValidationError):
        return unavailable_soai_path_response()
    return resolved, opened
