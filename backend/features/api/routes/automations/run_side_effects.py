"""SoAI - Automation run deletion side effects [backend/features/api/routes/automations/run_side_effects.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_identifiers import (
    build_automation_run_cancellation_id,
)
from core.automation.automation_run_task_lifecycle import (
    finalize_abandoned_automation_owner_task_ids,
    require_automation_identifier_list,
)
from core.tasks.cancellation import publish_cancel

if TYPE_CHECKING:
    from fastapi import Request

    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("process_occurrence_deletion_run_side_effects",)


async def process_occurrence_deletion_run_side_effects(
    request: Request,
    api_context: ApiContext,
    result: JSONDict,
) -> None:
    cancelled_run_ids = require_automation_identifier_list(
        result.get("cancelled_run_ids"),
        label="cancelled run ids",
    )
    abandoned_owner_task_ids = require_automation_identifier_list(
        result.get("abandoned_owner_task_ids"),
        label="abandoned owner task ids",
    )
    for run_id in cancelled_run_ids:
        await publish_cancel(
            api_context.dependencies.event_bus,
            api_context.dependencies.cancellation_coordinator,
            api_context.dependencies.cancellation_history,
            request.state.context,
            "Automation run deletion requested.",
            cancellation_id=build_automation_run_cancellation_id(run_id),
        )
    result.pop("abandoned_owner_task_ids")
    await finalize_abandoned_automation_owner_task_ids(
        api_context.dependencies.task_registry,
        abandoned_owner_task_ids,
        error_message="Automation run deleted.",
    )
