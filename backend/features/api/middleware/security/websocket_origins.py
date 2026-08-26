"""SoAI - API security WebSocket origin helpers [backend/features/api/middleware/security/websocket_origins.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.users.bootstrap_state import BootstrapState
from core.webui_manager.protocols import WebUIManagerProtocol
from features.api.middleware.security.same_origin import origin_matches_request_host

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "compile_websocket_origin_regex",
    "should_allow_websocket_bootstrap_origin",
    "websocket_origin_allowed",
)

LOGGER_NAME = "SoAI.features.api.websocket_origins"
OPERATION_API_SECURITY_COMPILE_WEBSOCKET_ORIGIN_REGEX = (
    "api_security.compile_websocket_origin_regex"
)
OPERATION_API_SECURITY_SHOULD_ALLOW_WEBSOCKET_BOOTSTRAP_ORIGIN = (
    "api_security.should_allow_websocket_bootstrap_origin"
)


def compile_websocket_origin_regex(
    pattern: str | None,
) -> re.Pattern[str] | None:
    if not pattern:
        return None
    try:
        return re.compile(pattern)
    except re.error as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Invalid WebSocket origin regex pattern",
            operation=OPERATION_API_SECURITY_COMPILE_WEBSOCKET_ORIGIN_REGEX,
            details={"pattern": pattern},
            level="warning",
        )
        return None


def websocket_origin_allowed(
    origin: str | None,
    cors_config: JSONDict | None,
    trusted_origins: tuple[str, ...],
    request_host: str | None,
    request_scheme: str | None,
) -> bool:
    origin_pattern_value = cors_config.get("allow_origin_regex") if cors_config else None
    origin_pattern = origin_pattern_value if isinstance(origin_pattern_value, str) else None
    normalized_pattern = str(origin_pattern or "").strip()
    has_regex = bool(origin_pattern)
    has_trusted = bool(trusted_origins)
    if not origin:
        if not has_regex and not has_trusted:
            return True
        if normalized_pattern in {"^.*$", ".*"}:
            return True
        return False
    if origin_matches_request_host(origin, request_host, request_scheme):
        return True
    if trusted_origins and origin in trusted_origins:
        return True
    if origin_pattern:
        regex = compile_websocket_origin_regex(origin_pattern)
        if regex and regex.fullmatch(origin):
            return True
    return False


async def should_allow_websocket_bootstrap_origin(
    webui_manager: WebUIManagerProtocol,
) -> bool:
    try:
        bootstrap_state = await webui_manager.get_bootstrap_state()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="WebSocket bootstrap state lookup failed (non-critical).",
            operation=OPERATION_API_SECURITY_SHOULD_ALLOW_WEBSOCKET_BOOTSTRAP_ORIGIN,
            level="debug",
        )
        return False
    return bootstrap_state is BootstrapState.UNINITIALIZED
