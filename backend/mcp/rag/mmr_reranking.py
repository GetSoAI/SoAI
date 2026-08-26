"""SoAI - Shared MCP RAG MMR reranking helpers [backend/mcp/rag/mmr_reranking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from mcp.storage.reranking import rerank_results

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("maybe_rerank_mmr_results",)


async def maybe_rerank_mmr_results(
    *,
    runtime_flags: RuntimeFlagsViewProtocol,
    logger: LoggerProtocol,
    query: str,
    mmr_result: JSONDict,
    rerank_config: JSONDict,
    operation: str,
    details: Mapping[str, JSONValue],
    failure_message: str,
) -> None:
    mmr_results_value = mmr_result.get("results")
    mmr_results = (
        [item for item in mmr_results_value if isinstance(item, dict)]
        if isinstance(mmr_results_value, list)
        else []
    )
    if not (rerank_config.get("rerank_enabled") and mmr_results):
        return
    try:
        mmr_result["results"] = await rerank_results(
            runtime_flags,
            query,
            mmr_results,
            dict(rerank_config),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        error_details = dict(details)
        error_details["failure_message"] = failure_message
        log_handled_exception(
            logger,
            exception,
            message="Failed to rerank MMR results (non-critical).",
            operation=operation,
            details=error_details,
            level="debug",
        )
