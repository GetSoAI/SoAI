"""SoAI - Automation scheduler cycle helpers [backend/app/background/automation_cycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.automation.automation_constants import (
    AUTOMATION_MAX_CONCURRENT_RUNS,
    AUTOMATION_SCHEDULER_DEFAULT_DUE_BATCH_LIMIT,
    AUTOMATION_SCHEDULER_DEFAULT_TICK_SECONDS,
)
from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError
from core.licensing.admission import LicensingOperationClass
from core.timing.epoch import epoch_ms
from core.validation.record_fields import require_int, require_non_empty_str

if TYPE_CHECKING:
    from app.background.internal_protocols import (
        AutomationSchedulingDependenciesProtocol,
    )
    from core.automation.protocols_database import (
        DatabaseAutomationRunSchedulerProtocol,
    )

__all__ = (
    "AutomationServiceSettings",
    "claim_due_automation_runs",
    "load_automation_service_settings",
)


@dataclass(frozen=True, slots=True)
class AutomationServiceSettings:
    tick_seconds: float
    due_batch_limit: int
    max_concurrent_runs: int
    max_concurrent_runs_per_user: int
    queue_size: int


def load_automation_service_settings(
    config: ConfigProtocol,
) -> AutomationServiceSettings:
    tick_seconds = coerce_positive_float(
        config.get("AUTOMATION.SCHEDULER_TICK_SECONDS"),
        default=AUTOMATION_SCHEDULER_DEFAULT_TICK_SECONDS,
        minimum=0.1,
        label="AUTOMATION.SCHEDULER_TICK_SECONDS",
    )
    due_batch_limit = coerce_positive_int(
        config.get("AUTOMATION.DUE_BATCH_LIMIT"),
        default=AUTOMATION_SCHEDULER_DEFAULT_DUE_BATCH_LIMIT,
        minimum=1,
        label="AUTOMATION.DUE_BATCH_LIMIT",
    )
    max_concurrent_runs = coerce_positive_int(
        config.get("AUTOMATION.MAX_CONCURRENT_RUNS"),
        default=AUTOMATION_MAX_CONCURRENT_RUNS,
        minimum=1,
        label="AUTOMATION.MAX_CONCURRENT_RUNS",
    )
    max_concurrent_runs_per_user = coerce_positive_int(
        config.get("AUTOMATION.MAX_CONCURRENT_RUNS_PER_USER"),
        default=1,
        minimum=1,
        label="AUTOMATION.MAX_CONCURRENT_RUNS_PER_USER",
    )
    return AutomationServiceSettings(
        tick_seconds=tick_seconds,
        due_batch_limit=due_batch_limit,
        max_concurrent_runs=max_concurrent_runs,
        max_concurrent_runs_per_user=max_concurrent_runs_per_user,
        queue_size=max(due_batch_limit, max_concurrent_runs),
    )


async def claim_due_automation_runs(
    api_dependencies: AutomationSchedulingDependenciesProtocol,
    database_automation_run_scheduler: DatabaseAutomationRunSchedulerProtocol,
    *,
    due_batch_limit: int,
    max_concurrent_runs_per_user: int,
    enqueue_run_id: Callable[[str], None],
) -> None:
    if not await _ordinary_automation_admission_allowed(api_dependencies):
        return
    now_ms = epoch_ms()
    active_run_counts = await database_automation_run_scheduler.count_active_runs_by_user()
    remaining_run_slots = due_batch_limit
    claimed_any = True
    while remaining_run_slots > 0 and claimed_any:
        claimed_any = False
        due_automations = await api_dependencies.database_automations.list_due_automations(
            now_ms,
            remaining_run_slots,
        )
        for automation_record in due_automations:
            if remaining_run_slots <= 0:
                return
            user_id = require_int(
                automation_record.get("user_id"),
                label="Automation service field 'user_id'",
                build_error=StateError,
                minimum=1,
            )
            existing_active_runs = active_run_counts.get(user_id, 0)
            if existing_active_runs >= max_concurrent_runs_per_user:
                continue
            user_remaining_slots = max_concurrent_runs_per_user - existing_active_runs
            automation_id = require_non_empty_str(
                automation_record.get("id"),
                label="Automation service field 'id'",
                build_error=StateError,
            )
            if not await _ordinary_automation_admission_allowed(api_dependencies):
                return
            claimed_runs = await api_dependencies.database_automations.claim_due_runs(
                automation_id,
                now_ms=now_ms,
                expected_next_run_at=require_int(
                    automation_record.get("next_run_at_ms"),
                    label="Automation service field 'next_run_at_ms'",
                    build_error=StateError,
                    minimum=1,
                ),
                max_run_slots=min(remaining_run_slots, user_remaining_slots),
            )
            if not claimed_runs:
                continue
            claimed_any = True
            remaining_run_slots -= len(claimed_runs)
            active_run_counts[user_id] = existing_active_runs + len(claimed_runs)
            for claimed_run in claimed_runs:
                if (
                    require_non_empty_str(
                        claimed_run.get("status"),
                        label="Automation service field 'status'",
                        build_error=StateError,
                    )
                    == "queued"
                ):
                    enqueue_run_id(
                        require_non_empty_str(
                            claimed_run.get("run_id"),
                            label="Automation service field 'run_id'",
                            build_error=StateError,
                        ),
                    )


async def _ordinary_automation_admission_allowed(
    api_dependencies: AutomationSchedulingDependenciesProtocol,
) -> bool:
    decision = await api_dependencies.licensing_service.admission(LicensingOperationClass.ORDINARY)
    return decision.allowed
