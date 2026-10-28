"""SoAI - Browser navigation error conversion [backend/mcp/tools/browser/navigation_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.public_projection import project_public_exception
from core.logging.trace import get_logger
from core.network.urls import redact_url_for_logging
from core.runtime.network_policy import is_loopback_host
from mcp.tools.browser.playwright_error_classification import (
    is_loopback_connection_refused_error,
    is_navigation_timeout_error,
    resolve_chromium_net_error_code,
)
from mcp.tools.browser.session_state import (
    mark_browser_session_from_playwright_exception,
)
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from typing import NoReturn

    from core.types.json import JSONDict
    from mcp.tools.browser.navigation_arguments import NavigateWaitUntil
    from mcp.tools.browser.types import BrowserSessionState

__all__ = ("raise_navigation_playwright_tool_error",)

LOGGER_NAME = "SoAI.mcp.tools.navigation_errors"
OPERATION_NAVIGATE = "mcp.browser.navigation_errors.navigate"
_NAVIGATION_RPC_CODE = -32603
_CONNECTION_REFUSED_ERROR_CODE = "ERR_CONNECTION_REFUSED"
_TLS_CERTIFICATE_ERROR_PREFIX = "ERR_CERT_"
_TLS_REJECTED_MESSAGE = (
    "Browser navigation was rejected because the site's TLS certificate is not trusted"
)


def raise_navigation_playwright_tool_error(
    state: BrowserSessionState,
    *,
    exception: BaseException,
    attempted_url: str,
    wait_until: NavigateWaitUntil,
) -> NoReturn:
    mark_browser_session_from_playwright_exception(state, exception=exception)
    classified = _classify_navigation_failure(
        state,
        exception=exception,
        attempted_url=attempted_url,
        wait_until=wait_until,
    )
    if classified is not None:
        raise classified from exception
    log_exception(
        get_logger(LOGGER_NAME),
        coerce_to_soai_error(exception, operation=OPERATION_NAVIGATE),
        message="Browser navigation failed unexpectedly.",
        operation=OPERATION_NAVIGATE,
        details={"attempted_url": redact_url_for_logging(attempted_url)},
        level="warning",
    )
    raise MCPToolError(
        _NAVIGATION_RPC_CODE,
        project_public_exception(exception).message,
    ) from exception


def _classify_navigation_failure(
    state: BrowserSessionState,
    *,
    exception: BaseException,
    attempted_url: str,
    wait_until: NavigateWaitUntil,
) -> MCPToolError | None:
    if is_navigation_timeout_error(exception):
        return MCPToolError(
            _NAVIGATION_RPC_CODE,
            "Browser navigation timed out before the page reached the requested load state.",
            data={
                "reason": "navigation_timeout",
                "attempted_url": str(attempted_url),
                "hint": (
                    "Retry with a larger timeout_ms."
                    if wait_until == "domcontentloaded"
                    else "Retry with wait_until='domcontentloaded' or a larger timeout_ms."
                ),
            },
        )
    loopback_data = _build_loopback_connection_refused_data(
        attempted_url=attempted_url,
        exception=exception,
    )
    if loopback_data is not None:
        return MCPToolError(
            _NAVIGATION_RPC_CODE,
            _build_network_error_message(_CONNECTION_REFUSED_ERROR_CODE),
            data=loopback_data,
        )
    net_error_code = resolve_chromium_net_error_code(exception)
    if net_error_code is None:
        return None
    if net_error_code.startswith(_TLS_CERTIFICATE_ERROR_PREFIX):
        data: JSONDict = {
            "reason": "tls_certificate_rejected",
            "attempted_url": str(attempted_url),
        }
        if not state.ignore_https_errors:
            data["hint"] = "Retry with accept_insecure=true only if you trust this site."
        return MCPToolError(
            _NAVIGATION_RPC_CODE,
            f"{_TLS_REJECTED_MESSAGE} ({net_error_code}).",
            data=data,
        )
    return MCPToolError(
        _NAVIGATION_RPC_CODE,
        _build_network_error_message(net_error_code),
        data={"reason": "navigation_network_error", "attempted_url": str(attempted_url)},
    )


def _build_network_error_message(net_error_code: str) -> str:
    return f"Browser navigation failed with network error {net_error_code}."


def _build_loopback_connection_refused_data(
    *,
    attempted_url: str,
    exception: BaseException,
) -> JSONDict | None:
    if not is_loopback_connection_refused_error(exception):
        return None
    parsed = urlparse(str(attempted_url or ""))
    if not is_loopback_host(parsed.hostname):
        return None
    return {
        "reason": "loopback_connection_refused",
        "attempted_url": str(attempted_url),
        "hint": (
            "The browser reached loopback but the connection was refused. Confirm the local "
            "server is still alive from the browser runtime; shell PTY cleanup can terminate "
            "shell-backgrounded children unless the server is started as a tracked background "
            "shell session or a separate process session."
        ),
    }
