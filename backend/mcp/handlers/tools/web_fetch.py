"""SoAI - MCP RAG web fetch tool handler [backend/mcp/handlers/tools/web_fetch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.runtime.network_policy import OfflineModeError, validate_local_only_url
from core.timing.formatting import utc_now
from mcp.handlers.tools.document_response_detection import is_probable_document_response
from mcp.handlers.tools.rag_tool_base import RAGToolBase
from mcp.handlers.tools.web_fetch_execution import await_web_fetch_operation
from mcp.handlers.tools.web_fetch_parsing import (
    require_extract_mode,
    resolve_effective_max_chars,
    resolve_include_screenshot,
    resolve_timeout_ms,
)
from mcp.handlers.tools.web_fetch_screenshot import capture_web_fetch_screenshot
from mcp.protocol.types import MCPJSONRPCError
from mcp.rag.scraper.text_formatting import resolve_extract_mode_content, truncate_text
from mcp.shared.protocol_arguments import get_required_str
from mcp.tools.browser.download_flow_hints import build_download_flow_hints
from mcp.tools.browser.playwright_error_classification import is_download_starting_message

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("WebFetchTool",)


def _require_no_rag_ingest_params(arguments: JSONDict) -> None:
    forbidden = (
        "persist_to_knowledge",
        "focus_query",
        "retrieval_strategy",
        "top_k",
        "similarity_threshold",
        "chunk_size",
        "chunk_overlap",
        "embedding_model",
        "chunking_strategy",
    )
    present = [key for key in forbidden if key in arguments and arguments.get(key) is not None]
    if present:
        raise MCPJSONRPCError(
            -32602,
            "RAG ingestion parameters are not supported by web_fetch. Use knowledge_web_fetch instead.",
        )


class WebFetchTool(RAGToolBase):
    async def __call__(self, arguments: JSONDict) -> JSONDict:
        url = get_required_str(arguments, "url")
        extract_mode = require_extract_mode(arguments)
        include_screenshot_requested = resolve_include_screenshot(arguments, default=True)
        timeout_ms = resolve_timeout_ms(arguments)
        _require_no_rag_ingest_params(arguments)
        try:
            await validate_local_only_url(
                self._deps.rag.mcp_search.runtime_flags,
                url,
                source="RAG web_fetch",
            )
        except OfflineModeError as exception:
            raise MCPJSONRPCError(-32603, str(exception)) from exception
        user_id = self._deps.require_authenticated_user_id("RAG web_fetch (web_fetch)")
        try:
            web_fetcher = self._deps.rag.mcp_search.web_fetcher
            adblock_service = web_fetcher.adblock_service if web_fetcher is not None else None
            max_chars = resolve_effective_max_chars(self._deps.rag.config, arguments)
            start_time = time.monotonic()
            fetched = await await_web_fetch_operation(
                self._deps.rag.mcp_search.fetch_url(url, user_id=user_id),
                timeout_ms=timeout_ms,
                url=url,
            )
            took_ms = int((time.monotonic() - start_time) * 1000)
            content, content_type = resolve_extract_mode_content(
                content=fetched.content,
                content_type=fetched.content_type,
                source_html=fetched.source_html,
                extract_mode=extract_mode,
            )
            source_url = fetched.source_url or url
            is_document_response = is_probable_document_response(
                final_url=source_url,
                content_type=str(content_type or ""),
            )
            truncated_content, truncated = truncate_text(content, max_chars=max_chars)
            fetched_at = utc_now().isoformat()
            screenshot_payload = None
            screenshot_error = None
            download_started = False
            include_screenshot = bool(include_screenshot_requested) and not is_document_response
            if include_screenshot:
                screenshot_payload, screenshot_error = await capture_web_fetch_screenshot(
                    config=self._deps.rag.config,
                    runtime_flags=self._deps.rag.mcp_search.runtime_flags,
                    storage_manager=self._deps.rag.storage_manager,
                    url=source_url,
                    source_html=fetched.source_html,
                    adblock_service=adblock_service,
                )
                if isinstance(screenshot_error, str) and is_download_starting_message(
                    screenshot_error,
                ):
                    is_document_response = True
                    download_started = True
                    screenshot_error = (
                        "Download started; screenshot unavailable. "
                        "Use browser_navigate(action='url', url=final_url) to capture the download, "
                        "then browser_downloads to obtain file_path."
                    )
            elif is_document_response and include_screenshot_requested:
                screenshot_error = (
                    "Document response detected; screenshot skipped. "
                    "Use read_document(url=final_url) instead."
                )
            result: JSONDict = {
                "url": url,
                "final_url": source_url,
                "title": fetched.title or "",
                "content_type": content_type,
                "extract_mode": extract_mode,
                "truncated": truncated,
                "max_chars": max_chars,
                "length": len(truncated_content),
                "raw_length": len(content),
                "took_ms": took_ms,
                "fetched_at": fetched_at,
                "content": truncated_content,
                "page_count": fetched.page_count,
                "persisted": False,
            }
            if is_document_response:
                final_url = source_url
                recommended_timeout = (
                    min(600, max(30, int(timeout_ms) // 1000))
                    if isinstance(timeout_ms, int) and timeout_ms > 0
                    else 30
                )
                recommended_max_chars = min(200_000, max_chars)
                result["read_document_hint"] = (
                    "Prefer read_document to read this URL as a document (supports OCR + chunked reads)."
                )
                result["read_document_args"] = {
                    "url": final_url,
                    "max_chars": int(recommended_max_chars),
                    "offset_chars": 0,
                    "parse_timeout_sec": int(recommended_timeout),
                }
            if download_started:
                result.update(build_download_flow_hints(url=source_url))
            if screenshot_payload is not None:
                result["screenshot"] = screenshot_payload
            if screenshot_error is not None:
                result["screenshot_error"] = screenshot_error
            return result
        except (TypeError, ValueError) as exception:
            raise MCPJSONRPCError(-32602, str(exception)) from exception
