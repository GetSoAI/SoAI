"""SoAI - OpenAI API key quota finalization for task outcomes [backend/orchestrator/execution/outcome_api_key_quotas.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
from core.logging.trace import get_logger
from core.quotas.api_key_quota_reservation_finalization import (
    finalize_quota_reservation_required,
)
from core.quotas.token_reservation_payloads import resolve_token_quota_reservation
from core.tasks.task import Task

__all__ = ("finalize_openai_api_key_quota",)

LOGGER_NAME = "SoAI.orchestrator.execution.outcome_api_key_quotas"
OPERATION = "orchestrator.execution.outcomes.finalize_openai_api_key_quota"


async def finalize_openai_api_key_quota(
    database_api_keys: DatabaseAPIKeysProtocol,
    task: Task,
    *,
    actual_units: int,
) -> None:
    api_key_id_value = task.metadata.get("api_key_id")
    api_key_id = (
        api_key_id_value if isinstance(api_key_id_value, str) and api_key_id_value else None
    )
    if api_key_id is None:
        return
    reservation_value = resolve_token_quota_reservation(task.metadata.get("quota"))
    if reservation_value is None:
        return
    logger = get_logger(LOGGER_NAME)
    await finalize_quota_reservation_required(
        database_api_keys=database_api_keys,
        key_id=api_key_id,
        reservation=reservation_value,
        actual_units=int(actual_units),
        logger=logger,
        trace_id=None,
        operation=OPERATION,
    )
