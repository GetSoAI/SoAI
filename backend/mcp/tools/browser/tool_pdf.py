"""SoAI - Browser tool: browser_pdf [backend/mcp/tools/browser/tool_pdf.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import hashlib
from typing import TYPE_CHECKING

from core.config.clamped_numeric import read_config_nonnegative_int
from core.mcp.argument_shapes import require_trimmed_bounded_string_value
from core.serialization.base64_values import encode_base64_ascii
from mcp.tools.argument_fields import require_allowed_keys
from mcp.tools.argument_scalars import (
    parse_optional_bool_strict,
    parse_optional_number_strict,
)
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_current_page,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.browser.timeouts import resolve_action_timeout_sec
from mcp.tools.error import MCPToolError, build_invalid_params_error

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_pdf",)

_DEFAULT_PDF_MAX_INLINE_BYTES = 1_000_000


def _resolve_pdf_max_inline_bytes(utility_tools: MCPUtilityToolsProtocol) -> int:
    return read_config_nonnegative_int(
        utility_tools.config,
        "TOOLS.MCP.BROWSER.PDF_MAX_INLINE_BYTES",
        _DEFAULT_PDF_MAX_INLINE_BYTES,
    )


def _resolve_bool(value: JSONValue, *, field_name: str) -> bool | None:
    return parse_optional_bool_strict(
        value,
        field_name=field_name,
        message=f"{field_name} must be a boolean when provided",
    )


def _resolve_page_ranges(value: JSONValue) -> str | None:
    if value is None:
        return None
    return require_trimmed_bounded_string_value(
        value,
        build_error=build_invalid_params_error,
        type_message="page_ranges must be a non-empty string when provided",
        empty_message="page_ranges must be a non-empty string when provided",
        max_length_message="page_ranges is too long",
        max_length=200,
    )


async def tool_browser_pdf(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset({"landscape", "print_background", "scale", "page_ranges"})
        | BROWSER_SESSION_PARAM_KEYS,
        tool_name="browser_pdf",
    )
    scale_value = parse_optional_number_strict(
        arguments.get("scale"),
        field_name="scale",
        min_value=0.1,
        max_value=2.0,
    )
    landscape = _resolve_bool(arguments.get("landscape"), field_name="landscape")
    print_background = _resolve_bool(
        arguments.get("print_background"),
        field_name="print_background",
    )
    page_ranges = _resolve_page_ranges(arguments.get("page_ranges"))

    _store, state = await require_existing_session(utility_tools, arguments=arguments)
    async with browser_action_lock(state), state.lock:
        await sync_session_state(utility_tools.config, state)
        page = require_current_page(state)
        await require_browser_page_output_allowed(
            utility_tools,
            page,
            tool_name="browser_pdf",
        )
        action_timeout_sec = resolve_action_timeout_sec(utility_tools)
        async with asyncio.timeout(float(action_timeout_sec) + 60.0):
            pdf_bytes = await page.pdf(
                landscape=landscape,
                print_background=print_background,
                scale=scale_value,
                page_ranges=page_ranges,
            )
        await require_browser_page_output_allowed(
            utility_tools,
            page,
            tool_name="browser_pdf",
        )
        if not isinstance(pdf_bytes, bytes | bytearray):
            raise MCPToolError(-32603, "Playwright returned an invalid PDF payload.")
        data = bytes(pdf_bytes)
        sha256 = hashlib.sha256(data).hexdigest()
        max_inline = _resolve_pdf_max_inline_bytes(utility_tools)
        if max_inline and len(data) > max_inline:
            return {
                "content_type": "application/pdf",
                "bytes": len(data),
                "sha256": sha256,
                "pdf_error": (
                    f"PDF is too large to return inline "
                    f"({len(data)} bytes > {max_inline} bytes)."
                ),
            }
        return {
            "content_type": "application/pdf",
            "bytes": len(data),
            "sha256": sha256,
            "pdf_base64": encode_base64_ascii(data),
        }
