"""SoAI - Automation deadline enforcement [backend/features/automation/execution_deadline.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.automation.automation_constants import AUTOMATION_TIMEOUT_REASON_PREFIX
from core.runtime.request_context import RequestContext
from core.tasks.cancellation import publish_cancel

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "build_timeout_reason",
    "enforce_automation_run_deadline",
)


def build_timeout_reason(max_run_minutes: int) -> str:
    return f"{AUTOMATION_TIMEOUT_REASON_PREFIX} exceeded max_run_minutes={max_run_minutes}"


async def enforce_automation_run_deadline(
    api_dependencies: ApiDependencies,
    *,
    request_context: RequestContext,
    max_run_minutes: int,
) -> None:
    if (
        not isinstance(max_run_minutes, int)
        or isinstance(max_run_minutes, bool)
        or max_run_minutes <= 0
    ):
        return
    await asyncio.sleep(max_run_minutes * 60.0)
    await publish_cancel(
        api_dependencies.event_bus,
        api_dependencies.cancellation_coordinator,
        api_dependencies.cancellation_history,
        request_context,
        build_timeout_reason(max_run_minutes),
    )
