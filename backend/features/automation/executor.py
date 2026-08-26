"""SoAI - Automation run execution orchestration [backend/features/automation/executor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_run_task_lifecycle import (
    ensure_automation_run_owner_task_attached,
    read_automation_run_owner_task_id,
)
from core.errors.exceptions import StateError
from core.licensing.admission import LicensingOperationClass
from core.licensing.enforcement import LICENSING_RESTRICTED_MESSAGE
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from features.automation.executor_orchestration import (
    execute_automation_run_orchestration,
)
from features.automation.run_terminal_transitions import (
    complete_automation_run_terminal,
    finalize_automation_run_task_terminal,
)

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("execute_automation_run",)

LOGGER_NAME = "SoAI.features.automation.executor"


async def execute_automation_run(api_dependencies: ApiDependencies, *, run_id: str) -> None:
    logger = get_logger(LOGGER_NAME)
    run_record = await api_dependencies.database_automation_runs.get_run_for_execution(run_id)
    if not isinstance(run_record, dict):
        return
    run_record = await ensure_automation_run_owner_task_attached(
        api_dependencies.database_automation_runs,
        api_dependencies.task_registry,
        run_record=run_record,
    )
    licensing_admission = await api_dependencies.licensing_service.admission(
        LicensingOperationClass.ORDINARY
    )
    if not licensing_admission.allowed:
        user_id_value = run_record.get("user_id")
        if isinstance(user_id_value, bool) or not isinstance(user_id_value, int):
            raise StateError("Accepted automation run is missing its user identity.")
        owner_task_id = read_automation_run_owner_task_id(run_record)
        await complete_automation_run_terminal(
            api_dependencies,
            run_id=run_id,
            user_id=user_id_value,
            final_status="error",
            status_message=LICENSING_RESTRICTED_MESSAGE,
        )
        await finalize_automation_run_task_terminal(
            api_dependencies,
            owner_task_id=owner_task_id,
            final_status="error",
            error_code=403,
            error_message=LICENSING_RESTRICTED_MESSAGE,
        )
        return
    running_record = await api_dependencies.database_automation_runs.mark_run_running(
        run_id,
        now_ms=epoch_ms(),
    )
    if running_record is None:
        return
    owner_task_id = read_automation_run_owner_task_id(
        running_record,
    ) or read_automation_run_owner_task_id(
        run_record,
    )
    await execute_automation_run_orchestration(
        api_dependencies=api_dependencies,
        logger=logger,
        run_id=run_id,
        run_record=run_record,
        owner_task_id=owner_task_id,
    )
