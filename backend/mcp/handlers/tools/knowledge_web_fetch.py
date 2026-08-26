"""SoAI - MCP RAG knowledge_web_fetch tool handler [backend/mcp/handlers/tools/knowledge_web_fetch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.numeric import require_strict_int_at_least
from core.errors.exceptions import ValidationError
from core.runtime.network_policy import OfflineModeError, validate_local_only_url
from mcp.handlers.tools.document_response_detection import is_probable_document_url
from mcp.handlers.tools.inputs import extract_ingest_params
from mcp.handlers.tools.rag_tool_base import RAGToolBase
from mcp.handlers.tools.retrieval_params import resolve_retrieval_params
from mcp.handlers.tools.web_fetch_execution import await_web_fetch_operation
from mcp.handlers.tools.web_fetch_parsing import (
    require_extract_mode,
    resolve_effective_max_chars,
    resolve_include_screenshot,
    resolve_timeout_ms,
)
from mcp.handlers.tools.web_fetch_screenshot import capture_web_fetch_screenshot
from mcp.protocol.types import MCPJSONRPCError
from mcp.rag.scraper.url_validation import canonicalize_fetch_cache_url
from mcp.shared.protocol_arguments import get_required_str
from mcp.tools.browser.download_flow_hints import build_download_flow_hints
from mcp.tools.browser.playwright_error_classification import is_download_starting_message

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("WebFetchKnowledgeTool",)

_FETCH_CONTEXT_MAX_TOP_K_KEY = "TOOLS.RAG.WEB.FETCH_CONTEXT.MAX_TOP_K"


def _require_no_unsupported_params(arguments: JSONDict) -> None:
    forbidden = ("persist_to_knowledge",)
    present = [key for key in forbidden if key in arguments and arguments.get(key) is not None]
    if present:
        raise MCPJSONRPCError(
            -32602,
            "persist_to_knowledge is not supported by knowledge_web_fetch. This tool always ingests.",
        )


class WebFetchKnowledgeTool(RAGToolBase):
    async def __call__(self, arguments: JSONDict) -> JSONDict:
        url = get_required_str(arguments, "url")
        extract_mode = require_extract_mode(arguments)
        include_screenshot = resolve_include_screenshot(arguments, default=True)
        timeout_ms = resolve_timeout_ms(arguments)
        _require_no_unsupported_params(arguments)
        try:
            await validate_local_only_url(
                self._deps.rag.mcp_search.runtime_flags,
                url,
                source="RAG knowledge_web_fetch",
            )
        except OfflineModeError as exception:
            raise MCPJSONRPCError(-32603, str(exception)) from exception
        conv_id, user_id = await self._auth.authorize_conversation(
            arguments,
            operation_label="RAG knowledge_web_fetch",
            authorization_operation="web_fetch_ingest",
        )
        if not isinstance(conv_id, str) or not conv_id.strip():
            raise MCPJSONRPCError(-32603, "Invalid conversation id")
        try:
            web_fetcher = self._deps.rag.mcp_search.web_fetcher
            adblock_service = web_fetcher.adblock_service if web_fetcher is not None else None
            max_chars = resolve_effective_max_chars(self._deps.rag.config, arguments)

            focus_query_raw = arguments.get("focus_query")
            focus_query = focus_query_raw.strip() if isinstance(focus_query_raw, str) else ""
            ingest_params = extract_ingest_params(self._deps.rag, arguments)
            chunk_size = ingest_params.get("chunk_size")
            chunk_overlap = ingest_params.get("chunk_overlap")
            embedding_model_id = ingest_params.get("embedding_model")
            chunking_strategy = ingest_params.get("chunking_strategy")
            if not isinstance(chunk_size, int):
                raise MCPJSONRPCError(-32602, "chunk_size must be an integer")
            if not isinstance(chunk_overlap, int):
                raise MCPJSONRPCError(-32602, "chunk_overlap must be an integer")
            if embedding_model_id is not None and not isinstance(embedding_model_id, str):
                raise MCPJSONRPCError(-32602, "embedding_model must be a string")
            if not isinstance(chunking_strategy, str):
                raise MCPJSONRPCError(-32602, "chunking_strategy must be a string")
            try:
                max_top_k = require_strict_int_at_least(
                    self._deps.rag.config.get_int(_FETCH_CONTEXT_MAX_TOP_K_KEY),
                    key=_FETCH_CONTEXT_MAX_TOP_K_KEY,
                    minimum=1,
                )
            except ValidationError as exception:
                raise MCPJSONRPCError(-32603, str(exception)) from exception
            retrieval_params = await resolve_retrieval_params(
                rag=self._deps.rag,
                conv_id=conv_id,
                arguments=arguments,
                top_k_max=max_top_k,
            )
            queued = await await_web_fetch_operation(
                self._deps.rag.web_fetch_ingest(
                    conv_id=conv_id,
                    user_id=user_id,
                    url=url,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    embedding_model_id=embedding_model_id,
                    chunking_strategy=chunking_strategy,
                    focus_query=focus_query,
                    retrieval_strategy=retrieval_params.retrieval_strategy,
                    top_k=retrieval_params.top_k,
                    similarity_threshold=retrieval_params.similarity_threshold,
                    return_extract_mode=extract_mode,
                    return_max_chars=max_chars,
                ),
                timeout_ms=timeout_ms,
                url=url,
            )
            canonical_url = canonicalize_fetch_cache_url(url)
            screenshot_payload = None
            screenshot_error = None
            is_document_url = is_probable_document_url(canonical_url)
            download_started = False
            if include_screenshot and not is_document_url:
                screenshot_payload, screenshot_error = await capture_web_fetch_screenshot(
                    config=self._deps.rag.config,
                    runtime_flags=self._deps.rag.mcp_search.runtime_flags,
                    storage_manager=self._deps.rag.storage_manager,
                    url=canonical_url,
                    adblock_service=adblock_service,
                )
                if isinstance(screenshot_error, str) and is_download_starting_message(
                    screenshot_error,
                ):
                    is_document_url = True
                    download_started = True
                    screenshot_error = (
                        "Download started; screenshot unavailable. "
                        f"Use browser_navigate(action='url', url={canonical_url!r}) to capture the download, "
                        "then browser_downloads to obtain file_path."
                    )
            elif include_screenshot and is_document_url:
                screenshot_error = (
                    "Document URL detected; screenshot skipped. "
                    f"Use read_document(url={canonical_url!r}) instead."
                )
            if isinstance(queued, dict):
                queued["persisted"] = True
                queued["extract_mode"] = extract_mode
                queued["max_chars"] = max_chars
                if is_document_url:
                    recommended_timeout = (
                        min(600, max(30, int(timeout_ms) // 1000))
                        if isinstance(timeout_ms, int) and timeout_ms > 0
                        else 30
                    )
                    queued["read_document_hint"] = (
                        "Prefer read_document to read this URL as a document (supports OCR + chunked reads)."
                    )
                    queued["read_document_args"] = {
                        "url": canonical_url,
                        "max_chars": int(min(200_000, max_chars)),
                        "offset_chars": 0,
                        "parse_timeout_sec": int(recommended_timeout),
                    }
                if screenshot_payload is not None:
                    queued["screenshot"] = screenshot_payload
                if screenshot_error is not None:
                    queued["screenshot_error"] = screenshot_error
                if download_started:
                    queued.update(build_download_flow_hints(url=canonical_url))
            return queued
        except (TypeError, ValueError) as exception:
            raise MCPJSONRPCError(-32602, str(exception)) from exception
