"""SoAI - NvAPI control observation and safe actuation predicate [backend/hardware/vendors/nvidia/nvapi_control_observation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import StateError

__all__ = ("NvApiControlObservation",)


@dataclass(frozen=True, slots=True)
class NvApiControlObservation:
    value: int | None
    mode: int | None
    user_meaning_verified: bool
    original_restorable: bool
    conversion_failure: StateError | None

    def requires_actuation(self, value: int | float | None, mode: int | str | None) -> bool:
        return (
            self.user_meaning_verified
            and self.original_restorable
            and (self.value, self.mode) != (value, mode)
        )
