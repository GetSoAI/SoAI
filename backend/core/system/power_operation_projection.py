"""SoAI - Public power operation field projection [backend/core/system/power_operation_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TypedDict

from core.system.power_operations import (
    PowerOperation,
    PowerOperationAction,
    PowerOperationStatus,
)

__all__ = ("PowerOperationPublicFields", "project_power_operation_public_fields")


class PowerOperationPublicFields(TypedDict):
    operation_id: str
    owner_id: int
    action: PowerOperationAction
    force: bool
    accepted_at_ms: int
    execute_at_ms: int
    status: PowerOperationStatus
    attempt_count: int
    dispatch_started_at_ms: int | None
    completed_at_ms: int | None
    result_code: str | None
    error_code: str | None


def project_power_operation_public_fields(
    operation: PowerOperation,
) -> PowerOperationPublicFields:
    return {
        "operation_id": operation.operation_id,
        "owner_id": operation.owner_id,
        "action": operation.action,
        "force": operation.force,
        "accepted_at_ms": operation.accepted_at_ms,
        "execute_at_ms": operation.execute_at_ms,
        "status": operation.status,
        "attempt_count": operation.attempt_count,
        "dispatch_started_at_ms": operation.dispatch_started_at_ms,
        "completed_at_ms": operation.completed_at_ms,
        "result_code": operation.result_code,
        "error_code": operation.error_code,
    }
