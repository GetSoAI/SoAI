"""SoAI - GPU preflight and user finalization authority [backend/core/hardware/gpu_control_operation_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_settings_contract import GPU_DIRECT_SETTING_FIELDS
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.validation.strings import require_canonical_trimmed_json_text

__all__ = (
    "GPUClockCombinationUnsupportedError",
    "GPUClockConversionUnavailableError",
    "GPUControlPreflightRejection",
    "GPUControlCommitIntent",
)


@dataclass(frozen=True, slots=True)
class GPUControlPreflightRejection:
    code: str
    diagnostic: str
    changed: Literal[False] = field(default=False, init=False)

    def __post_init__(self) -> None:
        require_canonical_trimmed_json_text(
            self.code, error_message="GPU preflight rejection code is invalid."
        )
        if not isinstance(self.diagnostic, str):
            raise ValidationError("GPU preflight diagnostic requires immutable private text.")


@dataclass(frozen=True, slots=True)
class GPUControlCommitIntent:
    user_fields: tuple[str, ...]
    expected_control_state_digest: str
    slot_id: str | None
    slot_signature: str | None
    apply_at_boot: bool | None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.user_fields, tuple)
            or not self.user_fields
            or any(
                not isinstance(value, str) or value not in GPU_DIRECT_SETTING_FIELDS
                for value in self.user_fields
            )
            or len(set(self.user_fields)) != len(self.user_fields)
        ):
            raise ValidationError("GPU commit intent requires distinct immutable user fields.")
        try:
            require_canonical_sha256_hexdigest(
                self.expected_control_state_digest, label="GPU expected control state digest"
            )
        except StateError as exception:
            raise ValidationError("GPU expected control state digest is invalid.") from exception
        if self.apply_at_boot is not None and not isinstance(self.apply_at_boot, bool):
            raise ValidationError("GPU commit boot intent must be explicit boolean or null.")
        if self.slot_id is None:
            if self.slot_signature is not None or self.apply_at_boot is True:
                raise ValidationError("Direct GPU commit cannot carry saved-slot authority.")
        elif (
            not isinstance(self.slot_id, str)
            or self.slot_id not in ("1", "2", "3")
            or not isinstance(self.slot_signature, str)
            or not self.slot_signature
        ):
            raise ValidationError("GPU slot commit requires its exact slot and saved signature.")


class GPUClockConversionUnavailableError(StateError):
    code: str | int = "gpu_clock_conversion_unavailable"


class GPUClockCombinationUnsupportedError(GPUClockConversionUnavailableError):
    code: str | int = "gpu_clock_combination_unsupported"
