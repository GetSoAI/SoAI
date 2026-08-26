"""SoAI - Durable power operation acceptance boundary [backend/features/api/routes/system/system_power_acceptance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Request

from core.errors.exceptions import ServiceUnavailableError
from core.system.power_operations import PowerOperation, PowerOperationAction
from core.timing.constants import CONTROL_TIMEOUT_SEC
from features.api.runtime.context import ApiContext
from features.api.runtime.idempotency import require_idempotency_key
from features.api.runtime.request_user_resolution import resolve_request_user_id

__all__ = ("accept_power_operation",)


async def accept_power_operation(
    request: Request,
    api_context: ApiContext,
    *,
    action: PowerOperationAction,
    force: bool,
    delay_ms: int,
) -> PowerOperation:
    try:
        return await asyncio.wait_for(
            api_context.dependencies.power_operation_supervisor.accept(
                operation_id=require_idempotency_key(request),
                owner_id=resolve_request_user_id(request),
                action=action,
                force=force,
                delay_ms=delay_ms,
            ),
            timeout=CONTROL_TIMEOUT_SEC,
        )
    except TimeoutError as exception:
        raise ServiceUnavailableError(
            "Power operation durable acceptance timed out. Retry with the same Idempotency-Key."
        ) from exception
