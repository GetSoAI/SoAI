"""SoAI - System power route response models [backend/features/api/routes/system/system_power_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from core.system.power_operation_projection import project_power_operation_public_fields
from core.system.power_operations import PowerOperation, PowerOperationAction, PowerOperationStatus

__all__ = (
    "AcceptedPowerOperationResponse",
    "PowerOperationResponse",
    "build_power_operation_response",
)


class AcceptedPowerOperationResponse(BaseModel):
    status: Literal["accepted"]
    operation_id: str = Field(min_length=1)
    action: PowerOperationAction
    execute_at_ms: int = Field(ge=0)


class PowerOperationResponse(BaseModel):
    operation_id: str = Field(min_length=1)
    owner_id: int = Field(ge=0)
    action: PowerOperationAction
    force: bool
    accepted_at_ms: int = Field(ge=0)
    execute_at_ms: int = Field(ge=0)
    status: PowerOperationStatus
    attempt_count: int = Field(ge=0)
    dispatch_started_at_ms: int | None = Field(default=None, ge=0)
    completed_at_ms: int | None = Field(default=None, ge=0)
    result_code: str | None = None
    error_code: str | None = None


def build_power_operation_response(operation: PowerOperation) -> PowerOperationResponse:
    return PowerOperationResponse(**project_power_operation_public_fields(operation))
