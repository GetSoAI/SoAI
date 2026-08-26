"""SoAI - Execution scope liveness detection [backend/core/execution/execution_scope_liveness.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.tasks.protocols import TokenCollectionProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView

__all__ = ("execution_scope_is_live",)


async def execution_scope_is_live(
    *,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    cancellation_id: str | None,
) -> bool:
    if cancellation_id is None or not cancellation_id.strip():
        return False
    normalized_cancellation_id = cancellation_id.strip()
    tasks = await task_registry_queries.query_active_filtered(
        cancellation_id=normalized_cancellation_id,
        limit=1,
    )
    if tasks:
        return True
    tokens = await token_collection.get_tokens_for_scope(normalized_cancellation_id)
    return bool(tokens)
