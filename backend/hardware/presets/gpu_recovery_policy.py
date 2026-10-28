"""SoAI - Validate GPU recovery targets and AMD clock policy evidence [backend/hardware/presets/gpu_recovery_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.hardware.gpu_recovery_records import GPURecoveryMember
from core.hardware.gpu_settings_contract import AMD_NATIVE_PERFORMANCE_MODES
from core.types.json import JSONDict
from core.validation.record_fields import require_number
from core.validation.strings import require_canonical_trimmed_json_text

__all__ = ("validate_recovery_requested_values",)


def validate_recovery_requested_values(
    settings: JSONDict,
    modes: JSONDict,
    units: JSONDict,
    members: tuple[GPURecoveryMember, ...],
) -> None:
    for field, requested_value in settings.items():
        if modes[field] not in ("auto", "manual"):
            raise ValidationError("GPU recovery requested mode is invalid.")
        require_canonical_trimmed_json_text(
            units[field], error_message="Invalid GPU recovery requested unit."
        )
        if field == "performance_mode":
            policies = tuple(member for member in members if member.field == field)
            if (
                requested_value != "manual"
                or modes[field] != "manual"
                or units[field] != "policy"
                or len(policies) != 1
                or not any(
                    member.field == "core_clock" and member.backend == "amd_overdrive"
                    for member in members
                )
            ):
                raise ValidationError("GPU recovery AMD clock policy is invalid.")
            policy = policies[0]
            if (
                policy.backend != "amd_overdrive"
                or policy.member_id != "performance"
                or policy.native_unit != "policy"
                or policy.domain_id is not None
                or policy.pstate_id is not None
            ):
                raise ValidationError("GPU recovery AMD policy evidence is invalid.")
            if (
                policy.requested_value is not None
                or policy.requested_mode != "manual"
                or policy.original_value is not None
                or policy.original_mode not in AMD_NATIVE_PERFORMANCE_MODES
            ):
                raise ValidationError("GPU recovery AMD policy targets are invalid.")
        elif requested_value != "auto":
            require_number(
                requested_value, label="GPU recovery requested value", build_error=ValidationError
            )
