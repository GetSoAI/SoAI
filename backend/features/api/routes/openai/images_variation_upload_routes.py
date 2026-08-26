"""SoAI - OpenAI image variation upload endpoint [backend/features/api/routes/openai/images_variation_upload_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from starlette.responses import Response

from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.events.types_models_requests import ImageVariationRequestReceived
from core.openai.openai_current_media import IMAGES_VARIATIONS_CREATE_MULTIPART_FIELDS
from features.api.routes.openai.image_upload_payloads import (
    build_openai_image_variation_upload_payloads,
)
from features.api.routes.openai.image_upload_quota_lifecycle import (
    make_upload_dispatch_error_handlers,
)
from features.api.routes.openai.streaming_upload_command_flow import (
    execute_openai_multipart_upload_flow,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingMultipartResult,
    )

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.openai_public.post(
        "/images/variations",
        tags=["OpenAI Image Generation"],
        dependencies=[openai_api_dependency()],
    )
    async def handle_image_variation(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        max_upload_bytes = resolve_upload_limit_bytes(
            api_context.dependencies.config,
            UploadLimitType.IMAGE,
        )

        async def build_payload(
            _task_id: str,
            parsed: StreamingMultipartResult,
            _staged_paths: list[str],
        ) -> tuple[JSONDict, JSONDict]:
            return await build_openai_image_variation_upload_payloads(
                api_context=api_context,
                parsed=parsed,
                max_upload_bytes=max_upload_bytes,
            )

        on_recoverable_dispatch_error, on_isolation_dispatch_error = (
            make_upload_dispatch_error_handlers(
                operation="images.variations",
                recoverable_message=(
                    "Failed to dispatch OpenAI image variation request (non-critical)."
                ),
                isolation_message=(
                    "Unhandled unexpected error while dispatching OpenAI image variation request."
                ),
            )
        )

        return await execute_openai_multipart_upload_flow(
            request,
            api_context=api_context,
            command_type=ImageVariationRequestReceived,
            audit_action="VARY_IMAGE",
            audit_target="image_variation",
            operation="images.variations",
            required_fields=frozenset(),
            allowed_fields=IMAGES_VARIATIONS_CREATE_MULTIPART_FIELDS - {"image"},
            required_file_fields=frozenset({"image"}),
            allowed_file_fields=frozenset({"image"}),
            max_file_bytes=max_upload_bytes,
            max_total_file_bytes=max_upload_bytes,
            build_payload=build_payload,
            on_recoverable_dispatch_error=on_recoverable_dispatch_error,
            on_isolation_dispatch_error=on_isolation_dispatch_error,
        )
