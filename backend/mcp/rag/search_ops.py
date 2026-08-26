"""SoAI - MCP RAG search operations [backend/mcp/rag/search_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_rag import (
    MCP_RAG_COUNTER_SEARCHES_FAILED,
    MCP_RAG_TIMING_SEARCH_LATENCY_MS,
)
from core.rag.parameter_validation import (
    normalize_retrieval_strategy,
    validate_similarity_threshold,
    validate_top_k,
)
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TASK_TYPE_RAG_SEARCH
from core.timing.monotonic import monotonic_ms
from mcp.progress_reporting import create_rag_task
from mcp.rag.embedding_model import resolve_embedding_model_with_precedence
from mcp.rag.linked_retrieval import (
    LinkedKnowledgeAugmentRequest,
    augment_results_with_linked_knowledge,
)
from mcp.rag.linked_strategy_queries import LinkedRetrievalParameters
from mcp.rag.search_ops_embedding import (
    generate_query_embedding_and_persist_effective_model_if_needed,
    load_collection_constraints,
    validate_embedding_dimensions_or_raise,
)
from mcp.rag.search_ops_metrics import (
    publish_search_completion_event_noncritical,
    record_search_metrics,
)
from mcp.rag.search_ops_strategy import run_search_strategy

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = ("search",)

LOGGER_NAME = "SoAI.mcp.rag.search_ops"


async def search(
    self: MCPRAGInternalProtocol,
    conv_id: str,
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.3,
    retrieval_strategy: str = "similarity",
    user_id: int = 0,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    validated_top_k = validate_top_k(top_k)
    validated_similarity_threshold = validate_similarity_threshold(similarity_threshold)
    normalized_retrieval_strategy = normalize_retrieval_strategy(retrieval_strategy)
    record_search_metrics(self, normalized_retrieval_strategy)
    start_time_ms = monotonic_ms()
    result: JSONDict = {"query": query, "results": [], "count": 0}
    search_succeeded = False
    if user_id and user_id > 0:
        conv_id = await self.resolve_conv_id_for_user(conv_id, user_id)
    expected_dims, collection_effective_model = await load_collection_constraints(self, conv_id)
    embedding_resolution = await resolve_embedding_model_with_precedence(
        self,
        conv_id,
        user_id,
        request_model=None,
    )
    resolved_embedding_model = embedding_resolution.model_id
    task = await create_rag_task(
        self.task_registry,
        task_type=TASK_TYPE_RAG_SEARCH,
        user_id=user_id,
        conv_id=conv_id,
        status=TaskStatus.WORKING,
        progress_total=100,
        metadata={
            "query": query,
            "retrieval_strategy": normalized_retrieval_strategy,
            "top_k": validated_top_k,
        },
    )
    try:
        query_vector, actual_model_value = (
            await generate_query_embedding_and_persist_effective_model_if_needed(
                self=self,
                query=query,
                conv_id=conv_id,
                user_id=user_id,
                resolved_embedding_model=resolved_embedding_model,
                expected_embedding_selector=embedding_resolution.stored_selector,
            )
        )
        if query_vector is None:
            await self.worker.complete_task(
                task.task_id,
                result={"count": 0},
                message="Search completed",
            )
            search_succeeded = True
            return result
        validate_embedding_dimensions_or_raise(
            expected_dims=expected_dims,
            query_vector=query_vector,
            request_model=resolved_embedding_model,
            actual_model=actual_model_value,
            collection_effective_model=collection_effective_model,
        )
        result = await run_search_strategy(
            self=self,
            logger=logger,
            conv_id=conv_id,
            query=query,
            query_vector=query_vector,
            top_k=validated_top_k,
            similarity_threshold=validated_similarity_threshold,
            retrieval_strategy=normalized_retrieval_strategy,
            user_id=user_id,
        )
        result = await augment_results_with_linked_knowledge(
            rag=self,
            request=LinkedKnowledgeAugmentRequest(
                conv_id=conv_id,
                user_id=user_id,
                parameters=LinkedRetrievalParameters(
                    query=query,
                    query_embedding=query_vector,
                    query_embedding_model=actual_model_value or resolved_embedding_model,
                    top_k=validated_top_k,
                    similarity_threshold=validated_similarity_threshold,
                    retrieval_strategy=normalized_retrieval_strategy,
                ),
            ),
            native_result=result,
        )
        await self.worker.complete_task(
            task.task_id,
            result={"count": result.get("count", 0)},
            message="Search completed",
        )
        search_succeeded = True
        return result
    except (SoAIError, RuntimeError, OSError, TypeError, ValueError) as exception:
        if self.metrics is not None:
            self.metrics.increment_counter(*MCP_RAG_COUNTER_SEARCHES_FAILED)
        await self.worker.fail_task(task.task_id, str(exception))
        raise
    finally:
        search_time_ms = max(0, monotonic_ms() - start_time_ms)
        if self.metrics is not None:
            self.metrics.record_timing(
                *MCP_RAG_TIMING_SEARCH_LATENCY_MS,
                duration_ms=float(search_time_ms),
            )
        if search_succeeded:
            await publish_search_completion_event_noncritical(
                self=self,
                logger=logger,
                conv_id=conv_id,
                query=query,
                retrieval_strategy=normalized_retrieval_strategy,
                search_time_ms=int(search_time_ms),
                result=result,
            )
