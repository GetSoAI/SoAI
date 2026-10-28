"""SoAI - Complete immutable native GPU plan composition [backend/hardware/gpu_tuning/native_plan_composition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import replace

from core.errors.exceptions import ValidationError
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingState,
    GPUPhysicalDevice,
    gpu_physical_device_observations,
)
from core.hardware.gpu_recovery_records import GPURecoveryRecord
from hardware.gpu_inventory.physical_binding import resolve_gpu_physical_binding
from hardware.gpu_tuning.control_recovery_records import recovery_member_key

__all__ = ("merge_prepared_native_records",)


def merge_prepared_native_records(
    target: GPUPhysicalDevice, operation_id: str, plans: list[GPURecoveryRecord]
) -> GPURecoveryRecord:
    if not plans:
        raise ValidationError("GPU preparation requires actual native members.")
    merged: GPURecoveryRecord = plans[0]
    for plan in plans:
        if plan.operation_id != operation_id or plan.device_id != target.device_id:
            raise ValidationError(
                "GPU native preparation changed canonical operation or device identity."
            )
    for plan in plans[1:]:
        if merged.pci_bdf_observations is None or plan.pci_bdf_observations is None:
            raise ValidationError("GPU native plans lack complete physical observations.")
        selected = gpu_physical_device_observations(
            replace(
                target,
                identity=merged.physical_identity,
                pci_bdf_observations=merged.pci_bdf_observations,
            )
        )
        candidate = gpu_physical_device_observations(
            replace(
                target,
                identity=plan.physical_identity,
                pci_bdf_observations=plan.pci_bdf_observations,
            )
        )
        binding = resolve_gpu_physical_binding(selected, [candidate])
        if binding.state != GPUPhysicalBindingState.BOUND or binding.device is None:
            raise ValidationError("GPU native original captures disagree on physical identity.")
        settings, modes, units = (
            copy.deepcopy(merged.requested_settings),
            copy.deepcopy(merged.requested_modes),
            copy.deepcopy(merged.requested_units),
        )
        for field in plan.requested_settings:
            if field in settings and (
                settings[field] != plan.requested_settings[field]
                or modes[field] != plan.requested_modes[field]
                or units[field] != plan.requested_units[field]
            ):
                raise ValidationError(
                    "GPU native plans conflict on internal field meaning or unit."
                )
            settings[field] = plan.requested_settings[field]
            modes[field] = plan.requested_modes[field]
            units[field] = plan.requested_units[field]
        members = merged.members + plan.members
        keys = tuple(recovery_member_key(member) for member in members)
        if len(set(keys)) != len(keys):
            raise ValidationError("GPU native plans duplicate an actual mutable member.")
        merged = replace(
            merged,
            backend="mixed",
            physical_identity=binding.device.identity,
            pci_bdf_observations=binding.device.pci_bdf_observations,
            requested_settings=settings,
            requested_modes=modes,
            requested_units=units,
            members=members,
        )
    return merged
