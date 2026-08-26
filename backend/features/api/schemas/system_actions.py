"""SoAI - System action schemas [backend/features/api/schemas/system_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

__all__ = (
    "ApplicationPowerActionRequest",
    "SystemActionRequest",
)


class SystemActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delay: StrictInt = Field(
        0,
        ge=0,
        le=86_400_000,
        description="Delay before executing the action, in milliseconds.",
    )
    force: StrictBool = False


class ApplicationPowerActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delay: StrictInt = Field(
        0,
        ge=0,
        le=86_400_000,
        description="Delay before executing the action, in milliseconds.",
    )
