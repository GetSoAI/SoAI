"""SoAI - Active conversation execution quiescence before deletion [backend/features/api/routes/webui/conversation_deletion_quiescence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.turn_record_fields import read_turn_optional_text
from core.automation.automation_identifiers import build_automation_run_cancellation_id
from core.errors.exceptions import ConflictError
from core.tasks.cancellation import publish_cancel
from core.timing.constants import CONTROL_TIMEOUT_SEC, TIGHT_POLL_INTERVAL_SEC

if TYPE_CHECKING:
    from fastapi import Request

    from features.api.runtime.context import ApiContext

__all__ = ("quiesce_conversations_before_deletion",)

SNAPSHOT_BATCH_SIZE = 16


@dataclass(frozen=True, slots=True)
class ConversationExecutionSnapshot:
    conv_id: str
    running_turn: bool
    active_task_count: int
    active_automation_run_count: int
    unfinalized_assistant_stream: bool
    cancellation_ids: tuple[str, ...]

    @property
    def execution_active(self) -> bool:
        return (
            self.running_turn or self.active_task_count > 0 or self.active_automation_run_count > 0
        )

    @property
    def active(self) -> bool:
        return self.execution_active or self.unfinalized_assistant_stream


async def _load_execution_snapshot(
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
) -> ConversationExecutionSnapshot:
    (
        running_turn,
        active_tasks,
        unfinalized_assistant_stream,
        active_automation_run_ids,
    ) = await asyncio.gather(
        api_context.dependencies.database_agent_turns.get_running_root_turn(
            conv_id=conv_id,
            user_id=user_id,
        ),
        api_context.dependencies.task_registry_queries.query_active_filtered(
            user_id=user_id,
            owner_type="conversation",
            owner_id=conv_id,
            exclude_cancellation_requested=False,
            limit=200000,
        ),
        api_context.dependencies.database_messages.has_unfinalized_assistant_stream(
            conv_id,
            user_id,
        ),
        api_context.dependencies.database_automation_runs.list_active_run_ids_for_conversation(
            user_id,
            conv_id=conv_id,
        ),
        return_exceptions=False,
    )
    cancellation_ids: list[str] = []
    for cancellation_id in (
        read_turn_optional_text(running_turn, "turn_cancellation_id"),
        read_turn_optional_text(running_turn, "active_inference_cancellation_id"),
        *(task.cancellation_id for task in active_tasks),
        *(build_automation_run_cancellation_id(run_id) for run_id in active_automation_run_ids),
    ):
        normalized_id = cancellation_id.strip() if isinstance(cancellation_id, str) else ""
        if normalized_id and normalized_id not in cancellation_ids:
            cancellation_ids.append(normalized_id)
    return ConversationExecutionSnapshot(
        conv_id=conv_id,
        running_turn=running_turn is not None,
        active_task_count=len(active_tasks),
        active_automation_run_count=len(active_automation_run_ids),
        unfinalized_assistant_stream=unfinalized_assistant_stream,
        cancellation_ids=tuple(cancellation_ids),
    )


async def _load_execution_snapshots(
    *,
    api_context: ApiContext,
    conv_ids: tuple[str, ...],
    user_id: int,
) -> tuple[ConversationExecutionSnapshot, ...]:
    snapshots: list[ConversationExecutionSnapshot] = []
    for batch_start in range(0, len(conv_ids), SNAPSHOT_BATCH_SIZE):
        batch_conv_ids = conv_ids[batch_start : batch_start + SNAPSHOT_BATCH_SIZE]
        batch_snapshot_awaitables: list[Awaitable[ConversationExecutionSnapshot]] = [
            _load_execution_snapshot(
                api_context=api_context,
                conv_id=conv_id,
                user_id=user_id,
            )
            for conv_id in batch_conv_ids
        ]
        snapshots.extend(
            await asyncio.gather(
                *batch_snapshot_awaitables,
                return_exceptions=False,
            ),
        )
    return tuple(snapshots)


async def _cancel_snapshot_execution(
    *,
    request: Request,
    api_context: ApiContext,
    snapshots: tuple[ConversationExecutionSnapshot, ...],
    reason: str,
    published_cancellation_ids: set[str],
) -> None:
    for snapshot in snapshots:
        if snapshot.execution_active and not snapshot.cancellation_ids:
            raise ConflictError(
                f"Conversation '{snapshot.conv_id}' has active execution with no cancellation scope.",
            )
        for cancellation_id in snapshot.cancellation_ids:
            if cancellation_id in published_cancellation_ids:
                continue
            await publish_cancel(
                api_context.dependencies.event_bus,
                api_context.dependencies.cancellation_coordinator,
                api_context.dependencies.cancellation_history,
                request.state.context,
                reason,
                cancellation_id=cancellation_id,
            )
            published_cancellation_ids.add(cancellation_id)


async def quiesce_conversations_before_deletion(
    *,
    request: Request,
    api_context: ApiContext,
    user_id: int,
    conv_ids: tuple[str, ...],
    reason: str,
    timeout_seconds: float = CONTROL_TIMEOUT_SEC,
) -> None:
    deduplicated_conv_ids = tuple(
        dict.fromkeys(conv_id for conv_id in conv_ids if conv_id and conv_id == conv_id.strip()),
    )
    if not deduplicated_conv_ids:
        return
    snapshots = await _load_execution_snapshots(
        api_context=api_context,
        conv_ids=deduplicated_conv_ids,
        user_id=user_id,
    )
    published_cancellation_ids: set[str] = set()
    await _cancel_snapshot_execution(
        request=request,
        api_context=api_context,
        snapshots=snapshots,
        reason=reason,
        published_cancellation_ids=published_cancellation_ids,
    )
    if not any(snapshot.active for snapshot in snapshots):
        return
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() < deadline:
        await asyncio.sleep(TIGHT_POLL_INTERVAL_SEC)
        snapshots = await _load_execution_snapshots(
            api_context=api_context,
            conv_ids=deduplicated_conv_ids,
            user_id=user_id,
        )
        await _cancel_snapshot_execution(
            request=request,
            api_context=api_context,
            snapshots=snapshots,
            reason=reason,
            published_cancellation_ids=published_cancellation_ids,
        )
        if not any(snapshot.active for snapshot in snapshots):
            return
    active_ids = ", ".join(snapshot.conv_id for snapshot in snapshots if snapshot.active)
    raise ConflictError(f"Conversation execution did not quiesce before deletion: {active_ids}")
