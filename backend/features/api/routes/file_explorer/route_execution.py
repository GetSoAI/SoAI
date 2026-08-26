"""SoAI - File explorer route execution error mapping [backend/features/api/routes/file_explorer/route_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from features.api.routes.file_explorer.route_exception_handling import (
    FILE_EXPLORER_ROUTE_EXCEPTIONS,
    handle_file_explorer_route_exception,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("execute_file_explorer_route_json",)


async def execute_file_explorer_route_json(
    *,
    request: Request,
    run: Callable[[], Awaitable[JSONDict]],
    logger: LoggerProtocol,
    recoverable_coerce_operation: str,
    operation: str,
    recoverable_log_message: str,
    server_error_message: str,
    handle_validation_error: bool = True,
) -> JSONResponse:
    try:
        payload = await run()
        return JSONResponse(content=payload)
    except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
        await handle_file_explorer_route_exception(
            request,
            exception=exception,
            logger=logger,
            coerce_operation=recoverable_coerce_operation,
            operation=operation,
            log_message=recoverable_log_message,
            server_error_message=server_error_message,
            handle_validation_error=handle_validation_error,
        )
