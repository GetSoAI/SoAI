"""SoAI - OpenAI image edit upload endpoint [backend/features/api/routes/openai/images_edit_upload_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import pydantic
from fastapi import Depends, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import Response

from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.errors.exceptions import ValidationError
from core.events.types_models_requests import (
    ImageEditJsonRequestReceived,
    ImageEditRequestReceived,
)
from core.openai.openai_current_media import IMAGES_EDITS_CREATE_MULTIPART_FIELDS
from core.validation.http_headers import content_type_is_json
from features.api.routes.openai.image_upload_payloads import (
    build_openai_image_edit_upload_payloads,
)
from features.api.routes.openai.image_upload_quota_lifecycle import (
    make_upload_dispatch_error_handlers,
)
from features.api.routes.openai.inference_dispatch import (
    handle_generic_inference_endpoint,
)
from features.api.routes.openai.streaming_upload_command_flow import (
    execute_openai_multipart_upload_flow,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.request_payloads import read_json_body
from features.api.schemas.openai_images import ImageEditJsonRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingMultipartResult,
    )

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.openai_public.post(
        "/images/edits",
        tags=["OpenAI Image Generation"],
        dependencies=[openai_api_dependency()],
    )
    async def handle_image_edit(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        if content_type_is_json(request.headers.get("content-type")):
            try:
                raw = await read_json_body(request, invalid_json_message="Invalid JSON.")
            except ValidationError as exception:
                raise RequestValidationError(
                    [{"loc": ("body",), "msg": "Invalid JSON.", "type": "value_error.jsondecode"}],
                    body=None,
                ) from exception
            try:
                payload = ImageEditJsonRequest.model_validate(raw)
            except pydantic.ValidationError as exception:
                raise RequestValidationError(exception.errors(), body=raw) from exception
            return await handle_generic_inference_endpoint(
                request,
                api_context,
                ImageEditJsonRequestReceived,
                "requests_total_image_edits",
                payload,
                ("image_edits",),
            )
        max_upload_bytes = resolve_upload_limit_bytes(
            api_context.dependencies.config,
            UploadLimitType.IMAGE,
        )

        async def build_payload(
            _task_id: str,
            parsed: StreamingMultipartResult,
            _staged_paths: list[str],
        ) -> tuple[JSONDict, JSONDict]:
            return await build_openai_image_edit_upload_payloads(
                api_context=api_context,
                parsed=parsed,
                max_upload_bytes=max_upload_bytes,
            )

        on_recoverable_dispatch_error, on_isolation_dispatch_error = (
            make_upload_dispatch_error_handlers(
                operation="images.edits",
                recoverable_message=(
                    "Failed to dispatch OpenAI image edit request (non-critical)."
                ),
                isolation_message=(
                    "Unhandled unexpected error while dispatching OpenAI image edit request."
                ),
            )
        )

        return await execute_openai_multipart_upload_flow(
            request,
            api_context=api_context,
            command_type=ImageEditRequestReceived,
            audit_action="EDIT_IMAGE",
            audit_target="image_edit",
            operation="images.edits",
            required_fields=frozenset({"prompt"}),
            allowed_fields=IMAGES_EDITS_CREATE_MULTIPART_FIELDS - {"image", "mask"},
            required_file_fields=frozenset({"image", "image[]"}),
            allowed_file_fields=frozenset({"image", "image[]", "mask"}),
            allow_multiple_files=True,
            max_file_bytes=max_upload_bytes,
            max_total_file_bytes=max_upload_bytes,
            build_payload=build_payload,
            on_recoverable_dispatch_error=on_recoverable_dispatch_error,
            on_isolation_dispatch_error=on_isolation_dispatch_error,
        )
