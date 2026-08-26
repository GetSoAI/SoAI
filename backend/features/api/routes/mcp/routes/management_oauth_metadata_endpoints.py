"""SoAI - MCP OAuth client metadata endpoint [backend/features/api/routes/mcp/routes/management_oauth_metadata_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.system_api.route_paths import MCP_OAUTH_CLIENT_METADATA_ROUTE_PATH
from features.api.routes.mcp.route_errors import (
    build_mcp_management_error_response,
)
from features.api.runtime.context import ApiContext, resolve_api_context

__all__ = ("register_endpoints",)

LOGGER_NAME = "SoAI.features.api.management_oauth_metadata_endpoints"
OPERATION = "api.mcp.oauth.client_metadata"


async def mcp_oauth_client_metadata(
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    try:
        document = api_context.dependencies.mcp_remote.build_oauth_client_metadata_document()
    except ValidationError as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="MCP OAuth client metadata is unavailable.",
            operation=OPERATION,
            level="warning",
        )
        return build_mcp_management_error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="MCP OAuth client metadata is unavailable.",
        )
    return JSONResponse(content=document)


def register_endpoints(router: APIRouter) -> None:
    router.get(MCP_OAUTH_CLIENT_METADATA_ROUTE_PATH)(mcp_oauth_client_metadata)
