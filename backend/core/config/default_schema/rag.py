"""SoAI - Default config schema: RAG [backend/core/config/default_schema/rag.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.network.outbound_http_profiles import DEFAULT_BROWSER_DOCUMENT_USER_AGENTS

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_rag_defaults",)


def build_rag_defaults() -> ConfigDict:
    return {
        "RAG": {
            "ENABLED": True,
            "CHROMA_PATH": "chroma_rag",
            "CHROMA_SHARD_COUNT": 1,
            "CHROMA_IPC_STARTUP_TIMEOUT_SEC": 10,
            "CHROMA_IPC_RETRY_COUNT": 1,
            "CHROMA_IPC_JOB_TTL_SEC": 3600,
            "CHROMA_QUERY_TIMEOUT_SEC": 30,
            "CHROMA_DELETE_TIMEOUT_SEC": 30,
            "CHROMA_ADD_TIMEOUT_SEC": 600,
            "CHROMA_ADD_CANCEL_WAIT_SEC": 2,
            "REINDEX_CHUNK_PAGE_SIZE": 256,
            "DEFAULT_EMBEDDING_MODEL": "auto",
            "PROCESSING_WORKERS": 3,
            "PROCESSING_QUEUE_SIZE": 1024,
            "PROCESSING_JOB_LEASE_TTL_SEC": 900,
            "EMBEDDING_TIMEOUT": 300,
            "EMBEDDING_RETRY_ATTEMPTS": 6,
            "EMBEDDING_BATCH_SIZE": 64,
            "EMBEDDING_MAX_BATCH_CHARS": 24000,
            "CHROMA_ADD_BATCH_SIZE": 64,
            "SPARSE_INDEX_DIR": "rag_sparse_index",
            "DEFAULT_CHUNK_SIZE": 500,
            "DEFAULT_CHUNK_OVERLAP": 100,
            "DEFAULT_TOP_K": 5,
            "DEFAULT_SIMILARITY_THRESHOLD": 0.3,
            "BRAVE": {
                "DEFAULT_SEARCH_LANG": "en",
                "DEFAULT_COUNTRY": "US",
            },
            "DUCKDUCKGO": {
                "BACKEND": "auto",
                "PROXY": "",
                "TIMEOUT": 10,
            },
            "GOOGLE": {
                "DEFAULT_SAFE": "active",
                "SEARCH_ENGINE_ID": "",
            },
            "SEARXNG": {
                "BASE_URL": "",
                "DEFAULT_CATEGORIES": ["general"],
                "ENGINES": [],
            },
            "SERPER": {
                "DEFAULT_GL": "us",
                "DEFAULT_HL": "en",
            },
            "TAVILY": {
                "DEFAULT_SEARCH_DEPTH": "basic",
                "INCLUDE_ANSWER": False,
            },
            "WEB": {
                "ENABLED": True,
                "DEFAULT_PROVIDER": "duckduckgo",
                "MAX_URL_SIZE_MB": 10,
                "REQUEST_TIMEOUT": 30,
                "FETCH_TOTAL_TIMEOUT_SEC": 30,
                "FETCH_VARIANTS_TOTAL_TIMEOUT_SEC": 35,
                "DNS_TIMEOUT_SEC": 5,
                "STREAM_CHUNK_SIZE": 65536,
                "HTML_PARSE_TIMEOUT": 15,
                "PDF_PARSE_TIMEOUT": 30,
                "CONTENT_MAX_CHARS": 120000,
                "CONTENT_TRIM_MODE": "sentence",
                "USER_AGENT": DEFAULT_BROWSER_DOCUMENT_USER_AGENTS[0],
                "ACCEPT_LANGUAGE": "en-US,en;q=0.9",
                "ACCEPT_HEADER": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "FETCH_RETRY_ATTEMPTS": 3,
                "FETCH_RETRY_DELAY": 2,
                "FETCH_CONTEXT": {
                    "MAX_TOP_K": 8,
                    "MAX_PASSAGE_CHARS": 700,
                    "MAX_TOTAL_CHARS": 2048,
                },
                "MARKDOWN": {
                    "STRIP_LINK_URLS": True,
                    "STRIP_IMAGES": True,
                },
                "URL_CACHE": {
                    "ENABLED": True,
                    "TTL_SEC": 3600,
                },
                "SEARCH_RETRY_ATTEMPTS": 3,
                "SEARCH_RETRY_DELAY": 2,
                "USER_AGENT_ROTATION": {
                    "ENABLED": True,
                    "MODE": "random",
                    "CUSTOM_AGENTS": [],
                },
                "PROXY": {
                    "ENABLED": False,
                    "HTTP_PROXY": "",
                    "HTTPS_PROXY": "",
                    "SOCKS5_PROXY": "",
                    "NO_PROXY": "localhost,127.0.0.1",
                    "ROTATION_ENABLED": False,
                    "PROXY_LIST": [],
                },
                "BROWSER_RENDER_ON_TIMEOUT_ENABLED": True,
                "BROWSER_RENDER_ON_HTTP_ERROR_ENABLED": True,
                "BROWSER_RENDER_ON_HTTP_ERROR_STATUS_CODES": [403, 429],
                "BROWSER_RENDER_HEADLESS": True,
                "BROWSER_RENDER_NAV_TIMEOUT_SEC": 30,
                "BROWSER_RENDER_STABILIZE_MS": 750,
                "BROWSER_RENDER_MAX_CONCURRENT_PAGES": 2,
                "BROWSER_RENDER_BLOCK_IMAGES": True,
                "BROWSER_RENDER_BLOCK_FONTS": True,
                "BROWSER_RENDER_BLOCK_MEDIA": True,
                "BROWSER_RENDER_BLOCK_ADS": True,
            },
        },
    }
