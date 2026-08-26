"""SoAI - MCP RAG search metrics and completion events [backend/mcp/rag/search_ops_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_mcp import RAGSearchCompletedEvent
from core.logging.protocols import LoggerProtocol
from core.metrics.keyspace_paths_mcp_rag import (
    MCP_RAG_COUNTER_SEARCHES_HYBRID,
    MCP_RAG_COUNTER_SEARCHES_MMR,
    MCP_RAG_COUNTER_SEARCHES_SIMILARITY,
    MCP_RAG_COUNTER_SEARCHES_TOTAL,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = (
    "publish_search_completion_event_noncritical",
    "record_search_metrics",
)

OPERATION = "mcp.rag.search_ops.publish_completed_event"


def record_search_metrics(self: MCPRAGInternalProtocol, retrieval_strategy: str) -> None:
    if self.metrics is None:
        return
    self.metrics.increment_counter(*MCP_RAG_COUNTER_SEARCHES_TOTAL)
    strategy_counter = {
        "mmr": MCP_RAG_COUNTER_SEARCHES_MMR,
        "hybrid": MCP_RAG_COUNTER_SEARCHES_HYBRID,
    }.get(retrieval_strategy, MCP_RAG_COUNTER_SEARCHES_SIMILARITY)
    self.metrics.increment_counter(*strategy_counter)


async def publish_search_completion_event_noncritical(
    *,
    self: MCPRAGInternalProtocol,
    logger: LoggerProtocol,
    conv_id: str,
    query: str,
    retrieval_strategy: str,
    search_time_ms: int,
    result: JSONDict,
) -> None:
    try:
        count_value = result.get("count", 0)
        results_count = (
            int(count_value)
            if isinstance(count_value, int | float) and not isinstance(count_value, bool)
            else 0
        )
        await self.event_bus.publish(
            RAGSearchCompletedEvent(
                conv_id=conv_id,
                query_length=len(query),
                results_count=results_count,
                retrieval_strategy=retrieval_strategy,
                search_time_ms=int(search_time_ms),
            ),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to publish RAG search completed event (non-critical).",
            operation=OPERATION,
            details={"conv_id": conv_id, "retrieval_strategy": retrieval_strategy},
            level="debug",
        )
