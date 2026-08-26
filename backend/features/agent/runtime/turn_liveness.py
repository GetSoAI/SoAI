"""SoAI - Agent turn liveness checks [backend/features/agent/runtime/turn_liveness.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_RUNNING
from core.agent.turn_record_fields import (
    read_turn_id,
    read_turn_int,
    read_turn_optional_text,
)
from core.execution.execution_scope_liveness import execution_scope_is_live
from core.runtime.boot_id import get_boot_id
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
    from core.tasks.protocols import TokenCollectionProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.types.json import JSONDict

__all__ = (
    "partition_running_root_turns_by_liveness",
    "turn_record_is_live",
    "turn_scope_is_live",
)

_RUNNING_TURN_CLAIM_GRACE_MS = 5_000


def _record_is_recent_running_turn(record: JSONDict) -> bool:
    status_value = record.get("status")
    status = status_value.strip().lower() if isinstance(status_value, str) else ""
    if status != AGENT_TURN_STATUS_RUNNING:
        return False
    updated_at_ms = read_turn_int(record, "updated_at_ms")
    if updated_at_ms is None or updated_at_ms < 0:
        return False
    return (epoch_ms() - updated_at_ms) <= _RUNNING_TURN_CLAIM_GRACE_MS


async def turn_scope_is_live(
    *,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    cancellation_id: str | None,
) -> bool:
    return await execution_scope_is_live(
        task_registry_queries=task_registry_queries,
        token_collection=token_collection,
        cancellation_id=cancellation_id,
    )


async def turn_record_is_live(
    *,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    record: JSONDict,
) -> bool:
    record_boot_id_value = record.get("server_boot_id")
    record_boot_id = record_boot_id_value.strip() if isinstance(record_boot_id_value, str) else ""
    if record_boot_id and record_boot_id != get_boot_id():
        return False
    if _record_is_recent_running_turn(record):
        return True
    turn_scope_active = await turn_scope_is_live(
        task_registry_queries=task_registry_queries,
        token_collection=token_collection,
        cancellation_id=read_turn_optional_text(record, "turn_cancellation_id"),
    )
    if turn_scope_active:
        return True
    return await turn_scope_is_live(
        task_registry_queries=task_registry_queries,
        token_collection=token_collection,
        cancellation_id=read_turn_optional_text(
            record,
            "active_inference_cancellation_id",
        ),
    )


async def partition_running_root_turns_by_liveness(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    conv_id: str,
    user_id: int,
    exclude_turn_id: str | None,
) -> tuple[list[JSONDict], list[JSONDict]]:
    running_turns = await database_agent_turns.get_running_root_turns(
        conv_id=conv_id,
        user_id=user_id,
    )
    normalized_exclude_turn_id = (
        exclude_turn_id.strip()
        if isinstance(exclude_turn_id, str) and exclude_turn_id.strip()
        else None
    )
    live_turns: list[JSONDict] = []
    stale_turns: list[JSONDict] = []
    for running_turn in running_turns:
        running_turn_id = read_turn_id(running_turn)
        if normalized_exclude_turn_id is not None and running_turn_id == normalized_exclude_turn_id:
            continue
        if await turn_record_is_live(
            task_registry_queries=task_registry_queries,
            token_collection=token_collection,
            record=running_turn,
        ):
            live_turns.append(running_turn)
        else:
            stale_turns.append(running_turn)
    return (live_turns, stale_turns)
