"""SoAI - MCP HTTP header negotiation helpers [backend/core/mcp/http_negotiation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math

from core.mcp.mcp_2025_11_25 import MCP_SESSION_ID_HEADER

__all__ = (
    "MCP_STREAMABLE_HTTP_JSON_MEDIA_TYPE",
    "MCP_STREAMABLE_HTTP_SSE_MEDIA_TYPE",
    "accept_supports_json",
    "accept_supports_sse",
    "build_mcp_streamable_http_headers",
    "resolve_streamable_http_post_response_mode",
    "split_accept_media_types",
)

MCP_STREAMABLE_HTTP_JSON_MEDIA_TYPE = "application/json"
MCP_STREAMABLE_HTTP_SSE_MEDIA_TYPE = "text/event-stream"


def split_accept_media_types(accept: str) -> list[str]:
    entries = _split_accept_entries(accept)
    if not entries:
        return ["*/*"]
    weighted_media_types = [
        (media_type, quality, index) for media_type, quality, index in entries if quality > 0.0
    ]
    if not weighted_media_types:
        return []
    return [
        media_type
        for media_type, _quality, _index in sorted(
            weighted_media_types,
            key=lambda item: (-item[1], item[2]),
        )
    ]


def _split_accept_entries(accept: str) -> list[tuple[str, float, int]]:
    if not accept:
        return []
    entries: list[tuple[str, float, int]] = []
    for index, entry in enumerate(accept.split(",")):
        parts = [part.strip() for part in entry.strip().split(";")]
        normalized = parts[0].lower() if parts else ""
        if not normalized:
            continue
        quality = _accept_entry_quality(parts[1:])
        entries.append((normalized, quality, index))
    return entries


def _accept_entry_quality(parameters: list[str]) -> float:
    for parameter in parameters:
        name, separator, value = parameter.partition("=")
        if separator and name.strip().lower() == "q":
            try:
                parsed = float(value.strip())
            except ValueError:
                return 1.0
            if not math.isfinite(parsed):
                return 0.0
            return max(0.0, min(1.0, parsed))
    return 1.0


def accept_supports_json(accept: str) -> bool:
    if (
        _accept_target_has_match(accept, MCP_STREAMABLE_HTTP_JSON_MEDIA_TYPE)
        and _accept_target_quality(accept, MCP_STREAMABLE_HTTP_JSON_MEDIA_TYPE) <= 0.0
    ):
        return False
    return any(
        media_type == MCP_STREAMABLE_HTTP_JSON_MEDIA_TYPE
        or media_type.endswith("+json")
        or media_type == "application/*"
        or media_type == "*/*"
        for media_type in split_accept_media_types(accept)
    )


def accept_supports_sse(accept: str) -> bool:
    if _accept_target_quality(accept, MCP_STREAMABLE_HTTP_SSE_MEDIA_TYPE) <= 0.0:
        return False
    return any(
        media_type in (MCP_STREAMABLE_HTTP_SSE_MEDIA_TYPE, "text/*", "*/*")
        for media_type in split_accept_media_types(accept)
    )


def resolve_streamable_http_post_response_mode(accept: str) -> str | None:
    json_supported = accept_supports_json(accept)
    sse_supported = accept_supports_sse(accept)
    for media_type in split_accept_media_types(accept):
        if json_supported and (
            media_type == MCP_STREAMABLE_HTTP_JSON_MEDIA_TYPE
            or media_type.endswith("+json")
            or media_type in {"application/*", "*/*"}
        ):
            return "json"
        if sse_supported and media_type in {MCP_STREAMABLE_HTTP_SSE_MEDIA_TYPE, "text/*", "*/*"}:
            return "sse"
    return None


def _accept_target_quality(accept: str, target_media_type: str) -> float:
    entries = _split_accept_entries(accept)
    if not entries:
        return 1.0
    matches: list[tuple[int, int, float]] = []
    for media_type, quality, index in entries:
        specificity = _accept_media_range_specificity(media_type, target_media_type)
        if specificity > 0:
            matches.append((specificity, index, quality))
    if not matches:
        return 0.0
    _specificity, _index, quality = sorted(matches, key=lambda item: (-item[0], item[1]))[0]
    return quality


def _accept_target_has_match(accept: str, target_media_type: str) -> bool:
    return any(
        _accept_media_range_specificity(media_type, target_media_type) > 0
        for media_type, _quality, _index in _split_accept_entries(accept)
    )


def _accept_media_range_specificity(media_type: str, target_media_type: str) -> int:
    if media_type == target_media_type:
        return 3
    target_type, separator, _target_subtype = target_media_type.partition("/")
    if not separator:
        return 0
    if media_type == f"{target_type}/*":
        return 2
    if media_type == "*/*":
        return 1
    return 0


def build_mcp_streamable_http_headers(session_id: str, *, sse: bool = False) -> dict[str, str]:
    if sse:
        return {
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            MCP_SESSION_ID_HEADER: session_id,
        }
    return {MCP_SESSION_ID_HEADER: session_id}
