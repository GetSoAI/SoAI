"""SoAI - OpenAI file upload route [backend/features/api/routes/openai/file_upload_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from features.api.routes.openai.file_upload_flow import execute_openai_file_upload_flow
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

__all__ = (
    "register_endpoints",
    "register_routes",
    "upload_file",
)


async def upload_file(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    return await execute_openai_file_upload_flow(request, api_context=api_context)


def register_endpoints(router: APIRouter) -> None:
    router.post("", status_code=200, dependencies=[openai_api_dependency()])(upload_file)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.openai_files)
