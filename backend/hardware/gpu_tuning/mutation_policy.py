"""SoAI - GPU tuning mutation policy responses [backend/hardware/gpu_tuning/mutation_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.hardware.types import GPUSettingsOutcome
from core.types.json import JSONDict

__all__ = (
    "HARDWARE_MUTATION_DISABLED_MESSAGE",
    "hardware_mutation_disabled_outcome",
    "hardware_mutation_disabled_payload",
)

HARDWARE_MUTATION_DISABLED_MESSAGE = (
    "Hardware mutation is disabled by SYSTEM.RUNTIME.HARDWARE_MUTATION_DISABLED."
)


def hardware_mutation_disabled_payload() -> JSONDict:
    return {
        "success": False,
        "code": "hardware_mutation_disabled",
        "error": HARDWARE_MUTATION_DISABLED_MESSAGE,
    }


def hardware_mutation_disabled_outcome() -> GPUSettingsOutcome:
    return GPUSettingsOutcome(
        success=False,
        status_code=503,
        payload=hardware_mutation_disabled_payload(),
        audit_action="gpu_settings_unavailable",
        audit_target="hardware_mutation_disabled",
        audit_details={},
        error_type="hardware_mutation_disabled",
        error_message=HARDWARE_MUTATION_DISABLED_MESSAGE,
    )
