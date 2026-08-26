"""SoAI - Automation run cancellation helpers for API routes [backend/features/api/runtime/automation_run_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.automation.automation_identifiers import build_automation_run_cancellation_id
from core.conversations.settings_authority import (
    resolve_conversation_settings_authority,
)
from core.runtime.protocols import RequestProtocol
from core.tasks.cancellation import publish_cancel
from core.types.json import JSONDict
from features.api.runtime.context import ApiContext

__all__ = (
    "publish_automation_run_cancellation_for_conversation",
    "publish_automation_run_cancellations_for_ids",
)


async def publish_automation_run_cancellations_for_ids(
    request: RequestProtocol,
    api_context: ApiContext,
    *,
    run_ids: tuple[str, ...],
    reason: str,
) -> None:
    for run_id in run_ids:
        await publish_cancel(
            api_context.dependencies.event_bus,
            api_context.dependencies.cancellation_coordinator,
            api_context.dependencies.cancellation_history,
            request.state.context,
            reason,
            cancellation_id=build_automation_run_cancellation_id(run_id),
        )


async def publish_automation_run_cancellation_for_conversation(
    request: RequestProtocol,
    api_context: ApiContext,
    *,
    conversation_record: JSONDict,
    user_id: int,
    conv_id: str,
    reason: str,
) -> None:
    if not resolve_conversation_settings_authority(conversation_record).is_automation:
        return
    active_run_ids = await api_context.dependencies.database_automation_runs.list_active_run_ids_for_conversation(
        user_id,
        conv_id=conv_id,
    )
    await publish_automation_run_cancellations_for_ids(
        request,
        api_context,
        run_ids=tuple(active_run_ids),
        reason=reason,
    )
