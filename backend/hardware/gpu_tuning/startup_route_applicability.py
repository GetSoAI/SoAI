"""SoAI - Startup native route applicability from actual obligations [backend/hardware/gpu_tuning/startup_route_applicability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_physical_identity import GPUInventoryReadState
from core.hardware.gpu_recovery_records import (
    GPUOriginalObservationState,
    GPURecoveryRecord,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from core.hardware.gpu_settings_contract import GPU_DIRECT_SETTING_FIELDS

if TYPE_CHECKING:
    from hardware.gpu_tuning.startup_scope_types import (
        GPUControlLegacyResetPlan,
        GPULegacyResetRoster,
    )

__all__ = (
    "GPUStartupRouteApplicability",
    "classify_startup_route",
    "require_applicable_startup_routes",
)

_COMPLETE_FACILITY_STATES = (
    GPUOriginalObservationState.OBSERVED,
    GPUOriginalObservationState.UNSUPPORTED,
)


class GPUStartupRouteApplicability(StrEnum):
    OBSERVED = "observed"
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    UNKNOWN = "unknown"


def classify_startup_route(
    roster: GPULegacyResetRoster,
    *,
    plan: GPUControlLegacyResetPlan,
    initial_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
) -> GPUStartupRouteApplicability:
    if roster.state == GPUInventoryReadState.OBSERVED:
        return GPUStartupRouteApplicability.OBSERVED
    if any(
        ("amd_smi" if member.backend == "amd_overdrive" else member.backend) == roster.backend
        for record in _recorded_children(initial_records)
        for member in record.members
    ):
        return GPUStartupRouteApplicability.REQUIRED
    if [
        vendor.state for vendor in plan.physical_snapshot.vendors if vendor.vendor == roster.vendor
    ] != [GPUInventoryReadState.OBSERVED]:
        return GPUStartupRouteApplicability.UNKNOWN
    for device in plan.devices:
        if device.target.vendor != roster.vendor:
            continue
        if (
            device.rejection is not None
            or not {facility.field for facility in device.facilities}.issuperset(
                GPU_DIRECT_SETTING_FIELDS
            )
            or any(
                facility.state not in _COMPLETE_FACILITY_STATES for facility in device.facilities
            )
        ):
            return GPUStartupRouteApplicability.UNKNOWN
    return GPUStartupRouteApplicability.NOT_REQUIRED


def require_applicable_startup_routes(
    rosters: tuple[GPULegacyResetRoster, ...],
    *,
    plan: GPUControlLegacyResetPlan,
    initial_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
    message: str,
) -> None:
    if any(
        classify_startup_route(roster, plan=plan, initial_records=initial_records)
        not in (GPUStartupRouteApplicability.OBSERVED, GPUStartupRouteApplicability.NOT_REQUIRED)
        for roster in rosters
    ):
        raise ValidationError(message)


def _recorded_children(
    records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
) -> tuple[GPURecoveryRecord, ...]:
    children: list[GPURecoveryRecord] = []
    for record in records:
        if isinstance(record, GPUStartupRecoveryRecord):
            children.extend((record.original_record, record.legacy_record))
        elif isinstance(record, GPUStartupLegacyRecoveryRecord):
            children.append(record.legacy_record)
        else:
            children.append(record)
    return tuple(children)
