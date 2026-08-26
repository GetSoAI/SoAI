"""SoAI - MCP http_request response payload building [backend/mcp/tools/http_request_response_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.files.content_types import (
    content_type_is_html,
    content_type_is_javascript,
    content_type_is_text,
    normalize_content_type,
)
from core.network.http_block_detection import detect_blocked_http_response
from core.serialization.base64_values import encode_base64_ascii

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_http_response_payload",
    "flatten_response_headers",
    "is_text_content_type",
    "read_response_body_with_limit",
)

_TEXT_PAYLOAD_MARKERS: frozenset[str] = frozenset(
    {
        "json",
        "xml",
        "yaml",
        "svg",
        "form",
    },
)


def is_text_content_type(content_type: str) -> bool:
    normalized = normalize_content_type(content_type)
    if (
        content_type_is_text(normalized)
        or content_type_is_html(normalized)
        or content_type_is_javascript(normalized)
    ):
        return True
    for marker in _TEXT_PAYLOAD_MARKERS:
        if marker in normalized:
            return True
    return False


def flatten_response_headers(raw_headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name_bytes, value_bytes in raw_headers:
        result[name_bytes.decode("latin-1").lower()] = value_bytes.decode("latin-1")
    return result


async def read_response_body_with_limit(
    response: httpx2.Response,
    *,
    max_response_bytes: int,
) -> tuple[bytes, bool]:
    limit_plus_one = max_response_bytes + 1
    buffer = bytearray()
    chunk_size = min(64 * 1024, limit_plus_one)
    async for chunk in response.aiter_bytes(chunk_size=chunk_size):
        if not chunk:
            continue
        remaining = limit_plus_one - len(buffer)
        if remaining <= 0:
            break
        if len(chunk) > remaining:
            buffer.extend(chunk[:remaining])
        else:
            buffer.extend(chunk)
        if len(buffer) >= limit_plus_one:
            break
    truncated = len(buffer) > max_response_bytes
    if truncated:
        buffer = buffer[:max_response_bytes]
    return (bytes(buffer), truncated)


def build_http_response_payload(
    *,
    response: httpx2.Response,
    request_url: str,
    method: str,
    elapsed_ms: int,
    raw_body: bytes,
    body_truncated: bool,
    retry_telemetry: dict[str, JSONValue],
    detect_blocked: bool,
) -> JSONDict:
    response_headers = flatten_response_headers(response.headers.raw)
    content_type = response_headers.get("content-type", "")
    if is_text_content_type(content_type):
        response_body = raw_body.decode("utf-8", errors="replace")
        encoding_label = "utf-8"
        body_text_for_detection: str | None = response_body
    else:
        response_body = encode_base64_ascii(raw_body)
        encoding_label = "base64"
        body_text_for_detection = None
    final_url = str(response.url)
    redirected = final_url != request_url
    blocked_info = None
    if detect_blocked:
        blocked_info = detect_blocked_http_response(
            status_code=int(response.status_code),
            url=final_url,
            redirected=bool(redirected),
            body_text=body_text_for_detection,
        )
    blocked = blocked_info is not None
    blocked_reason = blocked_info.reason if blocked_info is not None else None
    blocked_evidence = (
        {
            "match": blocked_info.match,
            "value": blocked_info.value,
            "url": blocked_info.url,
            "redirected": blocked_info.redirected,
            "snippet": blocked_info.snippet,
        }
        if blocked_info is not None
        else None
    )
    return {
        "status_code": int(response.status_code),
        "headers": response_headers,
        "body": response_body,
        "encoding": encoding_label,
        "url": final_url,
        "method": method,
        "elapsed_ms": elapsed_ms,
        "redirected": bool(redirected),
        "body_truncated": bool(body_truncated),
        "blocked": bool(blocked),
        "blocked_reason": blocked_reason,
        "blocked_evidence": blocked_evidence,
        "retry": dict(retry_telemetry),
    }
