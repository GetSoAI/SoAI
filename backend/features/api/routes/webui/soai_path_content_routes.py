"""SoAI - Conversation SoAI path content routes [backend/features/api/routes/webui/soai_path_content_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from functools import partial
from typing import TYPE_CHECKING

from fastapi import Depends, Query, Request, status
from starlette.responses import JSONResponse, Response

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import SecurityError, ValidationError
from core.files.document_type_detection import extract_extension, is_image_type
from core.serialization.json_parsing import parse_json_dict
from core.state.access import AccessAction
from core.validation.integers import is_non_negative_strict_int
from core.workspaces.soai_path_part_fields import target_fingerprint_value
from features.api.routes.webui.descriptor_content_response import (
    open_descriptor_streaming_response,
    open_descriptor_thumbnail_response,
)
from features.api.routes.webui.soai_path_operation_scope import (
    conversation_soai_path_scope,
)
from features.api.routes.webui.soai_path_operation_validation import (
    SoaiPathOperationRequest,
    canonical_soai_path_part,
    no_store_headers,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.webui_attachments.soai_path_snapshot import (
    open_verified_soai_path_file_descriptor,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)


def _unavailable_response() -> JSONResponse:
    return JSONResponse(
        content={"state": "unavailable"},
        status_code=status.HTTP_404_NOT_FOUND,
        headers=no_store_headers(),
    )


def _content_part_request(value: str) -> tuple[JSONDict, SoaiPathOperationRequest]:
    payload = parse_json_dict(value, field="content_part")
    return payload, SoaiPathOperationRequest(content_part=payload)


def _title(canonical: JSONDict) -> str:
    value = canonical.get("title")
    return value.strip() if isinstance(value, str) and value.strip() else "soai-path"


def _mime_type(canonical: JSONDict) -> str:
    value = canonical.get("mime_type")
    return value.strip() if isinstance(value, str) and value.strip() else "application/octet-stream"


def _size_bytes(canonical: JSONDict) -> int:
    value = canonical.get("size_bytes")
    if not is_non_negative_strict_int(value):
        raise ValidationError("SoAI path content size_bytes is invalid.")
    return value


def _is_image(canonical: JSONDict) -> bool:
    if canonical.get("preview_type") == "image":
        return True
    mime_type = canonical.get("mime_type")
    title = canonical.get("title")
    if not isinstance(mime_type, str) or not isinstance(title, str):
        return False
    return is_image_type(mime_type, extract_extension(title))


def _same_target(stored: JSONDict, canonical: JSONDict) -> bool:
    return target_fingerprint_value(stored) == target_fingerprint_value(canonical)


def _close_descriptor_if_present(descriptor: int | None) -> None:
    if descriptor is not None:
        os.close(descriptor)


async def _open_verified_descriptor(*, effective_root: str, canonical: JSONDict) -> int | None:
    descriptor_loader = partial(
        open_verified_soai_path_file_descriptor,
        effective_root=effective_root,
        canonical=canonical,
    )
    return await run_joined_thread_call(
        descriptor_loader,
        task_name="webui-soai-path-content-open",
        cancelled_result_cleanup=_close_descriptor_if_present,
    )


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get(
        "/conversations/{conv_id}/soai-paths/content",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def get_soai_path_content(
        request: Request,
        conv_id: str,
        content_part: str = Query(min_length=1),
        download: int = Query(default=0, ge=0, le=1),
        thumbnail: int = Query(default=0, ge=0, le=1),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            stored, body = _content_part_request(content_part)
            scope = await conversation_soai_path_scope(
                request=request,
                conv_id=conv_id,
                current_user=current_user,
                api_context=api_context,
            )
            canonical = canonical_soai_path_part(scope, body)
            if canonical.get("entry_type") != "file" or not _same_target(stored, canonical):
                return _unavailable_response()
            if int(thumbnail) == 1 and not _is_image(canonical):
                return _unavailable_response()
            descriptor = await _open_verified_descriptor(
                effective_root=scope.effective_root_real,
                canonical=canonical,
            )
            if descriptor is None:
                return _unavailable_response()
            if int(thumbnail) == 1:
                thumbnail_renderer = partial(
                    open_descriptor_thumbnail_response,
                    descriptor=descriptor,
                    filename=_title(canonical),
                )
                return await run_joined_thread_call(
                    thumbnail_renderer,
                    task_name="webui-soai-path-content-thumbnail",
                )
            return open_descriptor_streaming_response(
                descriptor=descriptor,
                size_bytes=_size_bytes(canonical),
                filename=_title(canonical),
                mime_type=_mime_type(canonical),
                download=int(download) == 1,
            )
        except (OSError, SecurityError, ValidationError):
            return _unavailable_response()
