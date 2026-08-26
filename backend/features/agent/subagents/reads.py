"""SoAI - Subagent state reads and stale reconciliation [backend/features/agent/subagents/reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import SUBAGENT_STATUS_RUNNING
from core.agent.turn_record_fields import read_turn_id, read_turn_int
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.execution.protocols import SubagentSnapshot
from features.agent.runtime.stale_turn_reconciliation import (
    persist_stale_turn_abandoned,
)
from features.agent.runtime.turn_liveness import turn_record_is_live
from features.agent.subagents.snapshots import (
    build_subagent_snapshot,
    build_subagent_snapshots,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TokenCollectionProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.types.json import JSONDict

__all__ = (
    "list_subagent_snapshots",
    "load_subagent_turn_record_noncritical",
    "read_subagent_snapshot",
)

OPERATION_LOAD_SUBAGENT_TURN_RECORD_NONCRITICAL = (
    "agent.subagents.reads.load_subagent_turn_record_noncritical"
)


async def read_subagent_snapshot(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    conv_id: str,
    user_id: int,
    subagent_id: str,
    parent_turn_id: str | None = None,
) -> SubagentSnapshot | None:
    turn_record = await database_agent_turns.get_subagent_turn(
        conv_id=conv_id,
        user_id=user_id,
        turn_id=subagent_id,
    )
    if not _turn_matches_parent(turn_record, parent_turn_id=parent_turn_id):
        return None
    reconciled_record = await _reconcile_subagent_turn_record(
        database_agent_turns=database_agent_turns,
        task_registry_queries=task_registry_queries,
        token_collection=token_collection,
        turn_record=turn_record,
    )
    if not _turn_matches_parent(reconciled_record, parent_turn_id=parent_turn_id):
        return None
    return build_subagent_snapshot(reconciled_record)


async def list_subagent_snapshots(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    conv_id: str,
    user_id: int,
    parent_turn_id: str | None = None,
    statuses: frozenset[str] | None = None,
) -> list[SubagentSnapshot]:
    turn_records = await database_agent_turns.list_subagent_summaries(
        conv_id=conv_id,
        user_id=user_id,
        parent_turn_id=parent_turn_id,
    )
    stale_subagent_ids = await _collect_stale_subagent_ids(
        task_registry_queries=task_registry_queries,
        token_collection=token_collection,
        turn_records=turn_records,
        parent_turn_id=parent_turn_id,
    )
    if stale_subagent_ids:
        for turn_record in turn_records:
            turn_id = str(turn_record.get("turn_id") or "").strip()
            if turn_id not in stale_subagent_ids:
                continue
            try:
                await persist_stale_turn_abandoned(
                    database_agent_turns=database_agent_turns,
                    record=turn_record,
                )
            except ValidationError:
                continue
        turn_records = await database_agent_turns.list_subagent_summaries(
            conv_id=conv_id,
            user_id=user_id,
            parent_turn_id=parent_turn_id,
        )
    snapshots = build_subagent_snapshots(turn_records)
    filtered_snapshots: list[SubagentSnapshot] = []
    for snapshot in snapshots:
        snapshot_parent_turn_id = snapshot.parent_turn_id
        if (
            isinstance(parent_turn_id, str)
            and parent_turn_id.strip()
            and snapshot_parent_turn_id != parent_turn_id.strip()
        ):
            continue
        if statuses is not None:
            status = snapshot.status
            if status not in statuses:
                continue
        filtered_snapshots.append(snapshot)
    return filtered_snapshots


async def load_subagent_turn_record_noncritical(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    logger: LoggerProtocol,
    trace_id: str,
    conv_id: str,
    user_id: int,
    subagent_id: str,
) -> JSONDict | None:
    try:
        return await database_agent_turns.get_subagent_turn(
            conv_id=conv_id,
            user_id=user_id,
            turn_id=subagent_id,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_LOAD_SUBAGENT_TURN_RECORD_NONCRITICAL,
        )
        log_handled_exception(
            logger,
            coerced,
            message="Failed to load subagent turn state (non-critical).",
            trace_id=trace_id,
            operation=OPERATION_LOAD_SUBAGENT_TURN_RECORD_NONCRITICAL,
            level="warning",
            details={"conv_id": conv_id, "turn_id": subagent_id},
        )
        return None


async def _collect_stale_subagent_ids(
    *,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    turn_records: list[JSONDict],
    parent_turn_id: str | None,
) -> set[str]:
    stale_subagent_ids: set[str] = set()
    normalized_parent_turn_id = (
        parent_turn_id.strip()
        if isinstance(parent_turn_id, str) and parent_turn_id.strip()
        else None
    )
    for turn_record in turn_records:
        if not _turn_matches_parent(turn_record, parent_turn_id=normalized_parent_turn_id):
            continue
        status = str(turn_record.get("status") or "").strip()
        if status != SUBAGENT_STATUS_RUNNING:
            continue
        if await turn_record_is_live(
            task_registry_queries=task_registry_queries,
            token_collection=token_collection,
            record=turn_record,
        ):
            continue
        subagent_id = str(turn_record.get("turn_id") or "").strip()
        if subagent_id:
            stale_subagent_ids.add(subagent_id)
    return stale_subagent_ids


async def _reconcile_subagent_turn_record(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    turn_record: JSONDict | None,
) -> JSONDict | None:
    if not isinstance(turn_record, dict):
        return None
    status = str(turn_record.get("status") or "").strip()
    if status != SUBAGENT_STATUS_RUNNING:
        return turn_record
    if await turn_record_is_live(
        task_registry_queries=task_registry_queries,
        token_collection=token_collection,
        record=turn_record,
    ):
        return turn_record
    try:
        await persist_stale_turn_abandoned(
            database_agent_turns=database_agent_turns,
            record=turn_record,
        )
    except ValidationError:
        return await _reload_subagent_turn_record(
            database_agent_turns=database_agent_turns,
            turn_record=turn_record,
        )
    return await _reload_subagent_turn_record(
        database_agent_turns=database_agent_turns,
        turn_record=turn_record,
    )


def _turn_matches_parent(
    turn_record: JSONDict | None,
    *,
    parent_turn_id: str | None,
) -> bool:
    if not isinstance(turn_record, dict):
        return False
    if parent_turn_id is None:
        return True
    return str(turn_record.get("parent_turn_id") or "").strip() == parent_turn_id


async def _reload_subagent_turn_record(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    turn_record: JSONDict,
) -> JSONDict | None:
    conv_id = str(turn_record.get("conv_id") or "").strip()
    user_id = read_turn_int(turn_record, "user_id")
    turn_id = read_turn_id(turn_record)
    if not conv_id or user_id is None or turn_id is None:
        return None
    return await database_agent_turns.get_subagent_turn(
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
    )
