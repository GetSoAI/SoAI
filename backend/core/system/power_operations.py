"""SoAI - Durable power operation contracts [backend/core/system/power_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = (
    "PowerOperation",
    "PowerOperationAction",
    "PowerOperationStatus",
)


class PowerOperationAction(str, Enum):
    APPLICATION_RESTART = "application_restart"
    APPLICATION_SHUTDOWN = "application_shutdown"
    HOST_SHUTDOWN = "host_shutdown"
    HOST_REBOOT = "host_reboot"
    HOST_SUSPEND = "host_suspend"
    HOST_HIBERNATE = "host_hibernate"


class PowerOperationStatus(str, Enum):
    SCHEDULED = "scheduled"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class PowerOperation:
    operation_id: str
    owner_id: int
    action: PowerOperationAction
    force: bool
    delay_ms: int
    accepted_at_ms: int
    execute_at_ms: int
    status: PowerOperationStatus
    claim_owner: str | None
    lease_expires_at_ms: int | None
    attempt_count: int
    dispatch_started_at_ms: int | None
    completed_at_ms: int | None
    result_code: str | None
    error_code: str | None
    active_slot: int | None
