"""SoAI - MCP scraper HTML parse bounded executor [backend/mcp/rag/scraper/html_parse_executor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    BoundedThreadPoolConfig,
    create_bounded_thread_pool_from_env,
)
from core.concurrency.bounded_pool_lifecycle import (
    resolve_lazy_bounded_pool,
    shutdown_lazy_bounded_pool,
)

__all__ = (
    "get_html_parse_executor",
    "shutdown_html_parse_executor",
)


class _HtmlParseExecutorState:
    executor: BoundedBlockingPool | None = None


def _create_html_parse_executor() -> BoundedBlockingPool:
    return create_bounded_thread_pool_from_env(
        BoundedThreadPoolConfig(
            label="rag_html_parse",
            thread_name_prefix="soai-rag-html-parse",
            max_workers_env="SOAI_RAG_HTML_PARSE_MAX_WORKERS",
            max_in_flight_env="SOAI_RAG_HTML_PARSE_MAX_IN_FLIGHT",
            default_max_workers=2,
            minimum_workers=1,
            maximum_workers=32,
            default_in_flight_multiplier=4,
            default_min_in_flight=8,
            max_in_flight_limit=2048,
        ),
    )


def get_html_parse_executor() -> BoundedBlockingPool:
    executor = resolve_lazy_bounded_pool(
        _HtmlParseExecutorState.executor,
        _create_html_parse_executor,
    )
    _HtmlParseExecutorState.executor = executor
    return executor


def shutdown_html_parse_executor() -> None:
    executor = _HtmlParseExecutorState.executor
    shutdown_lazy_bounded_pool(executor)
    _HtmlParseExecutorState.executor = None
