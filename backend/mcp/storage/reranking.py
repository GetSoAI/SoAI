"""SoAI - MCP storage reranking operations [backend/mcp/storage/reranking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from rerankers import Reranker
from rerankers.results import RankedResults

from core.config.numeric import coerce_positive_int
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.openai.payload_validation import RERANK_API_PROVIDERS
from core.runtime.network_policy import require_online_mode
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("rerank_results",)

LOGGER_NAME = "SoAI.mcp.storage.reranking"
OPERATION = "mcp.storage.rerank_results"


async def rerank_results(
    runtime_flags: RuntimeFlagsViewProtocol,
    query: str,
    results: list[JSONDict],
    rerank_config: JSONDict,
) -> list[JSONDict]:
    logger = get_logger(LOGGER_NAME)
    if not results:
        return results
    provider = str(rerank_config.get("rerank_provider", "cohere") or "cohere").strip().lower()
    if not provider:
        provider = "cohere"
    model_value = rerank_config.get("rerank_model")
    model = coerce_optional_trimmed_str(model_value if isinstance(model_value, str) else None)
    api_key = str(rerank_config.get("rerank_api_key") or "").strip()
    top_n = coerce_positive_int(
        rerank_config.get("rerank_top_n", len(results)),
        default=len(results),
        minimum=1,
    )
    top_n = min(top_n, len(results))
    if provider not in RERANK_API_PROVIDERS:
        raise ValidationError(f"Unsupported rerank_provider: {provider!r}")
    requires_api_key = True
    if requires_api_key and (not api_key):
        raise ValidationError(f"Reranking provider '{provider}' requires rerank_api_key.")
    require_online_mode(runtime_flags, source="Reranking API call")
    if model is None:
        model = provider
    try:
        if requires_api_key:
            ranker = Reranker(model, model_type=provider, api_key=api_key)
        else:
            ranker = Reranker(model, model_type=provider)
        if ranker is None:
            raise StateError("Reranker is not available.")
        docs: list[str] = [str(result_entry.get("content") or "") for result_entry in results]

        def _rank() -> RankedResults:
            return ranker.rank(query=query, docs=docs)

        ranked = await asyncio.to_thread(_rank)
        reranked: list[JSONDict] = []
        try:
            ranked_results = ranked.results
        except AttributeError as exception:
            raise StateError("Reranker returned an invalid response.") from exception
        if not isinstance(ranked_results, list):
            raise StateError("Reranker returned an invalid response.")
        for item in ranked_results[:top_n]:
            try:
                doc_id = item.doc_id
            except AttributeError as exception:
                raise StateError("Reranker returned an invalid doc_id.") from exception
            if not isinstance(doc_id, int) or doc_id < 0 or doc_id >= len(results):
                raise StateError("Reranker returned an invalid doc_id.")
            original = results[doc_id]
            reranked.append(
                {
                    **original,
                    "similarity": item.score,
                    "original_similarity": original.get("similarity", 0),
                    "rerank_position": len(reranked) + 1,
                },
            )
        logger.debug(
            "Reranked %s results to %s using %s/%s",
            len(results),
            len(reranked),
            provider,
            model,
        )
        return reranked
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Reranking failed",
            operation=OPERATION,
            details={"provider": provider, "model": model},
        )
        raise
