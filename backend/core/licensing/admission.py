"""SoAI - Licensing V1 admission decisions [backend/core/licensing/admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from core.licensing.status_resolution import licensing_state_requires_repair_plane
from core.licensing.types import LicensingState

__all__ = ("LicensingAdmissionDecision", "LicensingOperationClass", "resolve_licensing_admission")


class LicensingOperationClass(StrEnum):
    ORDINARY = "ordinary"
    REPAIR = "repair"


@dataclass(frozen=True, slots=True)
class LicensingAdmissionDecision:
    allowed: bool
    reason: LicensingState | Literal["restart_required"] | None
    repair_plane: bool


def resolve_licensing_admission(
    state: LicensingState,
    operation_class: LicensingOperationClass,
    *,
    requires_repair_plane: bool = False,
) -> LicensingAdmissionDecision:
    if operation_class is LicensingOperationClass.REPAIR:
        return LicensingAdmissionDecision(allowed=True, reason=None, repair_plane=True)
    state_requires_repair = licensing_state_requires_repair_plane(state)
    if requires_repair_plane or state_requires_repair:
        reason = state if state_requires_repair else "restart_required"
        return LicensingAdmissionDecision(allowed=False, reason=reason, repair_plane=False)
    return LicensingAdmissionDecision(allowed=True, reason=None, repair_plane=False)
