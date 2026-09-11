"""SoAI - MCP installed documentation search and read tool [backend/mcp/tools/soai_documentation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import difflib
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.documentation.relevance import DocumentationSearchResult, search_documentation_index
from core.documentation.search_index import build_documentation_search_index
from core.documentation.tokenization import build_query_groups
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.mcp.argument_numbers import parse_required_json_int_value
from core.serialization.json import serialize_json_compact_stable_strict
from core.text.chunked_reads import slice_chunked_text
from core.tool_calls.tool_result_prompt_settings import DEFAULT_TOOL_RESULT_PROMPT_MAX_CHARS
from mcp.tools.argument_fields import reject_unexpected_parameters, require_bounded_string
from mcp.tools.error import MCPToolError, build_invalid_params_error
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.documentation.bundle_parsing import DocumentationPage
    from core.types.json import JSONDict

__all__ = ("tool_soai_documentation",)

LOGGER_NAME = "SoAI.mcp.tools.soai_documentation"
OPERATION_SOAI_DOCUMENTATION = "mcp.tools.soai_documentation"
_ALLOWED_KEYS = frozenset({"query", "page", "max_results", "offset_chars", "max_chars"})
_MAX_CONTENT_CHARS = 12_000
_SEARCH_EXCERPT_CHARS = 2_000


def _parse_integer(
    arguments: JSONDict,
    field: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if field not in arguments:
        return default
    return parse_required_json_int_value(
        arguments[field],
        build_error=build_invalid_params_error,
        integer_message=f"{field} must be an integer",
        range_message=f"{field} must be between {minimum} and {maximum}",
        min_value=minimum,
        max_value=maximum,
    )


def _serialize_with_size(payload: JSONDict) -> tuple[JSONDict, int]:
    candidate = dict(payload)
    serialized_size = 0
    while True:
        candidate["serialized_response_chars"] = serialized_size
        next_size = len(serialize_json_compact_stable_strict(candidate, ensure_ascii=False))
        if next_size == serialized_size:
            return candidate, serialized_size
        serialized_size = next_size


def _find_excerpt_offset(result: DocumentationSearchResult) -> int:
    body_folded = result.record.body.casefold()
    positions = [
        position
        for surface in result.query_surfaces
        if (position := body_folded.find(surface.casefold())) >= 0
    ]
    if not positions:
        return 0
    return max(0, min(positions) - _SEARCH_EXCERPT_CHARS // 4)


def _search_result_payload(result: DocumentationSearchResult, max_chars: int) -> JSONDict:
    local_offset = _find_excerpt_offset(result)
    chunk = slice_chunked_text(
        content=result.record.body,
        max_chars=max_chars,
        offset_chars=local_offset,
        content_complete=True,
    )
    return {
        "page": result.record.page_id,
        "page_title": result.record.page_title,
        "section": result.record.section,
        "heading_path": list(result.record.heading_path),
        "score": result.score,
        "content": chunk.content,
        "offset_chars": result.record.start_offset + chunk.offset_chars,
        "next_offset_chars": (
            result.record.start_offset + chunk.next_offset_chars
            if chunk.next_offset_chars is not None
            else None
        ),
        "truncated": local_offset > 0 or chunk.truncated,
    }


def _build_search_payload(query: str, max_results: int) -> JSONDict:
    index = build_documentation_search_index()
    matches = search_documentation_index(index, query=query, max_results=max_results)
    selected = list(matches.results)
    excerpt_chars = _SEARCH_EXCERPT_CHARS
    while True:
        results = [_search_result_payload(result, excerpt_chars) for result in selected]
        payload: JSONDict = {
            "mode": "search",
            "query": matches.normalized_query,
            "total_matches": matches.total_matches,
            "returned_matches": len(results),
            "results": results,
            "truncated": matches.total_matches > len(results)
            or any(bool(result["truncated"]) for result in results),
            "max_serialized_response_chars": DEFAULT_TOOL_RESULT_PROMPT_MAX_CHARS,
        }
        finalized, size = _serialize_with_size(payload)
        if size <= DEFAULT_TOOL_RESULT_PROMPT_MAX_CHARS:
            return finalized
        if len(selected) > 1:
            selected.pop()
            continue
        if excerpt_chars > 1:
            excerpt_chars = max(1, excerpt_chars // 2)
            continue
        raise ValidationError("Documentation search response metadata exceeds its response budget")


def _page_payload(page: DocumentationPage, offset_chars: int, max_chars: int) -> JSONDict:
    content_limit = min(max_chars, _MAX_CONTENT_CHARS)
    while True:
        chunk = slice_chunked_text(
            content=page.content,
            max_chars=content_limit,
            offset_chars=offset_chars,
            content_complete=True,
        )
        warnings = list(chunk.warnings)
        if max_chars > content_limit and chunk.next_offset_chars is not None:
            warnings.append(
                f"Documentation response limited to {content_limit} characters; continue with offset_chars={chunk.next_offset_chars}."
            )
        payload: JSONDict = {
            "mode": "page",
            "page": page.page_id,
            "page_title": page.title,
            "section": page.section,
            "content": chunk.content,
            "offset_chars": chunk.offset_chars,
            "next_offset_chars": chunk.next_offset_chars,
            "returned_chars": len(chunk.content),
            "total_chars": len(page.content),
            "truncated": chunk.truncated,
            "warnings": warnings,
            "max_serialized_response_chars": DEFAULT_TOOL_RESULT_PROMPT_MAX_CHARS,
        }
        finalized, size = _serialize_with_size(payload)
        if size <= DEFAULT_TOOL_RESULT_PROMPT_MAX_CHARS:
            return finalized
        if content_limit <= 1:
            raise ValidationError(
                "Documentation page response metadata exceeds its response budget"
            )
        content_limit = max(1, content_limit - max(1, size - DEFAULT_TOOL_RESULT_PROMPT_MAX_CHARS))


def _read_page_payload(page_id: str, offset_chars: int, max_chars: int) -> JSONDict:
    index = build_documentation_search_index()
    page = index.corpus.pages_by_id.get(page_id)
    if page is None:
        suggestions = difflib.get_close_matches(
            page_id,
            tuple(index.corpus.pages_by_id),
            n=4,
            cutoff=0.55,
        )
        message = (
            f"Unknown documentation page ID '{page_id}'. "
            f"The installed bundle contains {len(index.corpus.pages)} pages; use query to find a canonical page ID."
        )
        if suggestions:
            message += f" Similar page IDs: {', '.join(suggestions)}."
        raise MCPToolError(-32602, message)
    return _page_payload(page, offset_chars, max_chars)


async def _run_documentation_operation(operation: Callable[[], JSONDict]) -> JSONDict:
    try:
        return await asyncio.to_thread(operation)
    except asyncio.CancelledError:
        raise
    except MCPToolError:
        raise
    except Exception as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION_SOAI_DOCUMENTATION)
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Installed documentation operation failed.",
            operation=OPERATION_SOAI_DOCUMENTATION,
        )
        raise MCPToolError(
            -32603,
            "The installed SoAI documentation is unavailable or invalid. Repair or update this SoAI installation and try again.",
        ) from exception


async def tool_soai_documentation(
    _utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    has_query = "query" in arguments
    has_page = "page" in arguments
    if has_query == has_page:
        raise MCPToolError(-32602, "Must provide exactly one of: query or page")
    if has_query:
        query = require_bounded_string(arguments["query"], field="query", max_length=4096)
        if "offset_chars" in arguments or "max_chars" in arguments:
            raise MCPToolError(-32602, "offset_chars and max_chars are only valid in page mode")
        max_results = _parse_integer(arguments, "max_results", default=5, minimum=1, maximum=20)
        try:
            build_query_groups(query)
        except ValidationError as exception:
            raise MCPToolError(-32602, exception.message) from exception
        return await _run_documentation_operation(lambda: _build_search_payload(query, max_results))
    page_id = require_bounded_string(arguments["page"], field="page", max_length=256)
    if "max_results" in arguments:
        raise MCPToolError(-32602, "max_results is only valid in search mode")
    offset_chars = _parse_integer(
        arguments,
        "offset_chars",
        default=0,
        minimum=0,
        maximum=50_000_000,
    )
    max_chars = _parse_integer(arguments, "max_chars", default=20_000, minimum=1, maximum=200_000)
    return await _run_documentation_operation(
        lambda: _read_page_payload(page_id, offset_chars, max_chars)
    )
