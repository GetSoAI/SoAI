"""SoAI - MCP utility tool definition: http_request [backend/mcp/tools/utility_tool_definitions/http_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_HTTP

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_http_request_tool_definitions",)

HTTP_METHODS: tuple[str, ...] = (
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
)


def build_http_request_tool_definitions() -> dict[str, JSONDict]:
    return {
        "http_request": {
            "title": "HTTP Request",
            "description": "Perform HTTP request (returns status, headers, body, timing). Text is UTF-8; binary is base64. Retries are automatic for safe methods and require Idempotency-Key for mutating methods. Supports session persistence (cookies/headers).",
            "icons": [build_tool_icon_entry(ICON_HTTP)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["url"],
                "properties": {
                    "url": {"type": "string", "description": "Target URL."},
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET default).",
                        "enum": list(HTTP_METHODS),
                    },
                    "headers": {
                        "type": "object",
                        "description": "Request headers.",
                        "additionalProperties": {"type": "string"},
                    },
                    "body": {
                        "type": "string",
                        "description": "Request body (POST/PUT/PATCH).",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (max 120).",
                    },
                    "follow_redirects": {
                        "type": "boolean",
                        "description": "Follow HTTP redirects.",
                    },
                    "max_response_bytes": {
                        "type": "integer",
                        "description": "Body size limit (sets body_truncated=true if reached).",
                    },
                    "detect_blocked": {
                        "type": "boolean",
                        "description": "Detect bot/CAPTCHA blocks (403/429).",
                    },
                    "retries": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 10,
                        "description": "Retry count for transient failures. POST, PUT, PATCH, and DELETE require a non-empty Idempotency-Key request header when this is greater than zero.",
                    },
                    "retry_backoff_min_ms": {
                        "type": "integer",
                        "minimum": 10,
                        "maximum": 60000,
                        "description": "Min exponential backoff delay.",
                    },
                    "retry_backoff_max_ms": {
                        "type": "integer",
                        "minimum": 10,
                        "maximum": 60000,
                        "description": "Max backoff delay.",
                    },
                    "retry_jitter_max_ms": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 10000,
                        "description": "Max random jitter for backoff.",
                    },
                    "retry_on_timeouts": {
                        "type": "boolean",
                        "description": "Retry on network timeouts.",
                    },
                    "retry_on_request_errors": {
                        "type": "boolean",
                        "description": "Retry on transport/connect errors.",
                    },
                    "retry_on_status": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 100, "maximum": 599},
                        "description": "Status codes to retry (e.g., 429, 502+).",
                    },
                    "session_mode": {
                        "type": "boolean",
                        "description": "Enable session persistence (returns cookies/headers).",
                    },
                    "session": {
                        "type": "object",
                        "additionalProperties": False,
                        "description": "Session payload (cookies/headers).",
                        "properties": {
                            "cookies": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["name", "value"],
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "string"},
                                        "domain": {"type": "string"},
                                        "path": {"type": "string"},
                                    },
                                },
                            },
                            "default_headers": {
                                "type": "object",
                                "additionalProperties": {"type": "string"},
                            },
                            "per_host_headers": {
                                "type": "object",
                                "additionalProperties": {
                                    "type": "object",
                                    "additionalProperties": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "status_code": {"type": "integer", "description": "HTTP status code."},
                    "headers": {
                        "type": "object",
                        "description": "Response headers.",
                        "additionalProperties": {"type": "string"},
                    },
                    "body": {
                        "type": "string",
                        "description": "Response body (UTF-8 or base64).",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "Body encoding (utf-8 or base64).",
                    },
                    "url": {"type": "string", "description": "Final URL."},
                    "method": {"type": "string"},
                    "elapsed_ms": {
                        "type": "integer",
                        "description": "Duration in ms.",
                    },
                    "redirected": {
                        "type": "boolean",
                        "description": "Redirected flag.",
                    },
                    "body_truncated": {
                        "type": "boolean",
                        "description": "Truncated flag.",
                    },
                    "blocked": {
                        "type": "boolean",
                        "description": "Blocked/CAPTCHA flag.",
                    },
                    "blocked_reason": {"type": ["string", "null"]},
                    "blocked_evidence": {"type": ["object", "null"]},
                    "retry": {
                        "type": "object",
                        "description": "Retry telemetry.",
                    },
                    "session": {
                        "type": "object",
                        "description": "Updated session.",
                    },
                },
            },
            "annotations": build_tool_annotation_flags(open_world=True),
        },
    }
