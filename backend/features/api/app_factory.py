"""SoAI - FastAPI app construction for the unified API surface [backend/features/api/app_factory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError, SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.state.access import AccessAction
from core.system_api.route_paths import (
    OPENAI_OPENAPI_SCHEMA_PATH,
    SOAI_API_OPENAPI_SCHEMA_PATH,
)
from features.api.rate_limiting.rate_limit_dependency import rate_limit_dependency
from features.api.runtime.access_dependencies import (
    openai_api_dependency,
    require_action_dependencies,
)
from features.api.runtime.context import get_request_trace_id
from features.api.runtime.project_root_files import read_text_file_from_project_root

__all__ = ("build_api_app",)

LOGGER_NAME = "SoAI.features.api.app_factory"
OPERATION = "api_core.docs_readme"


def build_api_app() -> FastAPI:
    app = FastAPI(
        title="SoAI Unified API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get(
        SOAI_API_OPENAPI_SCHEMA_PATH,
        include_in_schema=False,
        dependencies=[Depends(rate_limit_dependency), openai_api_dependency()],
    )
    @app.get(
        OPENAI_OPENAPI_SCHEMA_PATH,
        include_in_schema=False,
        dependencies=[Depends(rate_limit_dependency), openai_api_dependency()],
    )
    async def openapi_schema(_: Request) -> JSONResponse:
        return JSONResponse(content=app.openapi())

    docs_dependencies = require_action_dependencies(AccessAction.AUTH_COOKIE)

    @app.get("/docs", include_in_schema=False, dependencies=docs_dependencies)
    @app.get("/redoc", include_in_schema=False, dependencies=docs_dependencies)
    async def docs_readme(request: Request) -> Response:
        trace_id = get_request_trace_id(request)
        try:
            _filename, contents = await asyncio.to_thread(
                read_text_file_from_project_root,
                ("README.md",),
            )
        except NotFoundError as exception:
            raise NotFoundError(
                "README.md not found.",
                trace_id=trace_id,
                cause=exception,
                operation="api_core.docs_readme",
            ) from exception
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Failed to read README.md for /docs.",
                trace_id=trace_id,
                operation=OPERATION,
                level="error",
            )
            raise SoAIError(
                "Failed to read README.md.",
                trace_id=trace_id,
                cause=exception,
                operation="api_core.docs_readme",
            ) from exception
        return Response(content=contents, media_type="text/markdown; charset=utf-8")

    return app
