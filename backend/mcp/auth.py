"""SoAI - MCP authentication helpers [backend/mcp/auth.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Awaitable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.rag.config_metadata import parse_rag_config_metadata_value
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "parse_config_metadata",
    "resolve_with_auth_errors",
)

LOGGER_NAME = "SoAI.mcp.auth"
OPERATION = "mcp.auth.resolve_with_auth_errors"


def _normalize_not_found_message(exception: NotFoundError) -> str:
    message = str(exception).strip()
    match = re.match(r"Conversation not found for user_id=\d+: '([^']+)'.*", message)
    if match:
        conv_id = match.group(1)
        return f"Conversation not found: {conv_id}"
    if message:
        return message
    return "Requested resource was not found"


async def resolve_with_auth_errors[T](coro: Awaitable[T]) -> T:
    logger = get_logger(LOGGER_NAME)
    try:
        return await coro
    except NotFoundError as exception:
        raise MCPJSONRPCError(-32602, _normalize_not_found_message(exception)) from exception
    except ValueError as exception:
        raise MCPJSONRPCError(-32602, f"Access denied: {exception}") from exception
    except MCPJSONRPCError:
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Authorization check failed",
            operation=OPERATION,
        )
        raise MCPJSONRPCError(-32603, "Authorization check failed") from exception


def parse_config_metadata(config: JSONDict) -> JSONDict:
    try:
        return parse_rag_config_metadata_value(config.get("config_metadata"))
    except ValidationError as exception:
        raise MCPJSONRPCError(-32603, str(exception)) from exception
