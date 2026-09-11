"""SoAI - Authenticated optional plugin artwork responses [backend/features/api/routes/plugins/plugin_logo_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib

from fastapi import Depends, Request
from starlette.responses import Response

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.serialization.sha256_hexdigest import is_canonical_sha256_hexdigest
from core.state.access import AccessAction
from core.validation.identifiers import is_identifier_strictly_alnum
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

LOGO_PREPARATION_ERRORS: tuple[type[Exception], ...] = (
    StateError,
    ValidationError,
    OSError,
) + RECOVERABLE_EXCEPTIONS
LOGGER_NAME = "SoAI.features.api.plugin_logo_routes"
OPERATION_PREPARE_PLUGIN_LOGO = "plugins.logo.prepare"

__all__ = ("register_routes",)


def _matches_entity_tag(value: str | None, entity_tag: str) -> bool:
    if value is None or len(value) > 8 * 1024:
        return False
    return any(
        candidate.strip().removeprefix("W/") in (entity_tag, "*") for candidate in value.split(",")
    )


def register_routes(routers: ApiRouters) -> None:
    path = "/{plugin_name}/logo/{archive_sha256}.png"
    dependencies = require_action_dependencies(AccessAction.PLUGIN_READ)

    @routers.plugins.api_route(
        path,
        methods=["GET"],
        dependencies=dependencies,
        operation_id="get_plugin_logo",
    )
    async def get_plugin_logo(
        request: Request,
        plugin_name: str,
        archive_sha256: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        if not is_identifier_strictly_alnum(plugin_name) or not is_canonical_sha256_hexdigest(
            archive_sha256
        ):
            return Response(status_code=404, headers={"Cache-Control": "no-store"})
        try:
            result = await api_context.dependencies.plugin_manager.prepare_logo(
                plugin_name, archive_sha256
            )
        except LOGO_PREPARATION_ERRORS as exception:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Plugin artwork preparation unavailable",
                operation=OPERATION_PREPARE_PLUGIN_LOGO,
                details={"plugin": plugin_name},
                level="debug",
            )
            return Response(status_code=503, headers={"Cache-Control": "no-store"})
        if result is None or result.status != "available":
            return Response(status_code=404, headers={"Cache-Control": "no-store"})
        etag = f'"{hashlib.sha256(result.content).hexdigest()}"'
        headers = {
            "Cache-Control": "private, no-cache",
            "Content-Length": str(len(result.content)),
            "ETag": etag,
            "X-Content-Type-Options": "nosniff",
        }
        if _matches_entity_tag(request.headers.get("if-none-match"), etag):
            return Response(status_code=304, headers=headers)
        return Response(
            content=b"" if request.method == "HEAD" else result.content,
            media_type="image/png",
            headers=headers,
        )

    routers.plugins.add_api_route(
        path,
        get_plugin_logo,
        methods=["HEAD"],
        dependencies=dependencies,
        operation_id="head_plugin_logo",
    )
