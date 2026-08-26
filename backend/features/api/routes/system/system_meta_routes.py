"""SoAI - System metadata and limits routes [backend/features/api/routes/system/system_meta_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator

from fastapi import Depends, Request, status
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from pydantic import BaseModel
from starlette.responses import Response

from core.config.byte_sizes import MIB_BYTES
from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.errors.exceptions import ValidationError
from core.files.export import build_content_disposition_inline
from core.filesystem.async_queries import async_path_exists
from core.meta.instance_identity import (
    build_instance_identity_payload,
    persist_instance_name,
    resolve_instance_identity,
)
from core.state.access import AccessAction
from core.types.json import JSONDict
from core.types.json_value import filter_json_mapping_strict
from features.api.middleware.acl_enforcement import (
    deny_if_licensing_restricted,
    request_has_action,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_bad_request
from features.api.runtime.system_about import (
    load_public_system_info_payload,
    load_system_info_payload,
    load_system_license_payload,
    load_system_requirements_text,
)

__all__ = ("register_routes",)

_EMBEDDED_API_TEST_SUITE = "<html><head><title>SoAI API Test Suite</title></head><body><h1>SoAI API Test Suite</h1><p>This instance does not ship with soai_test_api.html. Use API clients or import a test plan.</p></body></html>"
_REQUIREMENTS_FILENAME = "requirements.txt"


def _iter_text_payload(text: str) -> Iterator[bytes]:
    yield text.encode("utf-8")


class InstanceNameUpdate(BaseModel):
    instance_name: str | None = None


def register_routes(routers: ApiRouters) -> None:
    @routers.system.get(
        "/test-suite",
        include_in_schema=False,
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def serve_test_suite(_: Request) -> Response:
        test_suite_path = os.path.join(os.path.dirname(__file__), "soai_test_api.html")
        if await async_path_exists(test_suite_path):
            return FileResponse(test_suite_path)
        return HTMLResponse(content=_EMBEDDED_API_TEST_SUITE, status_code=status.HTTP_200_OK)

    @routers.system.get("/health")
    async def system_health_check(
        _request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        identity = await resolve_instance_identity(
            api_context.dependencies.database_plugins,
            api_context.dependencies.database_licensing,
        )
        runtime_api_endpoint = api_context.dependencies.runtime_state.runtime_api_endpoint
        if runtime_api_endpoint is None:
            raise ValidationError("Runtime API endpoint is unavailable.")
        licensing_status = await api_context.dependencies.licensing_service.resolved_status()
        payload: JSONDict = {
            "status": (
                "degraded"
                if licensing_status.requires_repair_plane
                or api_context.dependencies.runtime_state.degraded_mode
                else "ok"
            ),
            "edition": api_context.dependencies.licensing_policy.edition,
            "power_operations": (
                "healthy"
                if api_context.dependencies.power_operation_supervisor.is_ready
                else "degraded"
            ),
        }
        identity_payload = filter_json_mapping_strict(
            build_instance_identity_payload(identity),
            error_message="Instance identity payload must be JSON-compatible.",
        )
        payload.update(identity_payload)
        payload.update(runtime_api_endpoint.to_public_payload())
        return JSONResponse(content=payload)

    @routers.system.put(
        "/instance-name",
        dependencies=require_action_dependencies(AccessAction.CONFIG_PATCH),
    )
    async def update_instance_name(
        request: Request,
        payload: InstanceNameUpdate,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            instance_name = await persist_instance_name(
                api_context.dependencies.database_plugins,
                payload.instance_name,
            )
        except ValidationError as exception:
            raise_bad_request(
                request,
                str(exception),
                error_type="invalid_instance_name",
            )
        log_audit_event(
            request,
            action="system.instance_name.update",
            target="instance_name",
            details={"instance_name": instance_name},
        )
        return JSONResponse(content={"instance_name": instance_name})

    @routers.system.get("/limits")
    async def get_system_limits(
        _request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        max_file_upload_bytes = resolve_upload_limit_bytes(
            api_context.dependencies.config,
            UploadLimitType.FILE,
        )
        max_file_upload_mb = max_file_upload_bytes / MIB_BYTES
        camera_vision_upload_enabled = api_context.dependencies.config.get_bool(
            "SERVER.WEBUI.CHAT.CAMERA_VISION_UPLOAD_ENABLED",
        )
        camera_vision_image_optimization_enabled = api_context.dependencies.config.get_bool(
            "SERVER.WEBUI.CHAT.CAMERA_VISION_IMAGE_OPTIMIZATION_ENABLED",
        )
        return JSONResponse(
            content={
                "max_file_upload_bytes": max_file_upload_bytes,
                "max_file_upload_mb": int(max_file_upload_mb),
                "camera_vision_upload_enabled": bool(camera_vision_upload_enabled),
                "camera_vision_image_optimization_enabled": bool(
                    camera_vision_image_optimization_enabled,
                ),
            },
        )

    @routers.system.get("/info")
    async def system_info(
        request: Request,
    ) -> Response:
        if not await request_has_action(request, AccessAction.SYSTEM_STATUS_READ):
            deny_if_licensing_restricted(request)
            return JSONResponse(content=load_public_system_info_payload())
        payload = await asyncio.to_thread(
            load_system_info_payload,
        )
        return JSONResponse(content=payload)

    @routers.system.get("/license")
    async def system_license(
        _request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        payload = await asyncio.to_thread(
            load_system_license_payload,
            project_root=api_context.dependencies.base_dir,
            policy=api_context.dependencies.licensing_policy,
        )
        return JSONResponse(content=payload, headers={"Cache-Control": "no-store"})

    @routers.system.get(
        "/requirements",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def system_requirements(_: Request) -> Response:
        requirements_text = await asyncio.to_thread(load_system_requirements_text)
        headers = {
            "Content-Disposition": build_content_disposition_inline(_REQUIREMENTS_FILENAME),
            "Cache-Control": "no-store",
        }
        return StreamingResponse(
            _iter_text_payload(requirements_text),
            media_type="text/plain; charset=utf-8",
            headers=headers,
        )
