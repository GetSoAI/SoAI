"""SoAI - Observed NVIDIA architecture contracts [backend/core/hardware/gpu_architecture.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json import is_json_dict
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import require_int_in_range_strict

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.hardware.gpu_physical_identity import (
        GPUPhysicalDevice,
        GPUPhysicalIdentity,
        GPUPhysicalSnapshot,
    )
    from core.types.json import JSONDict, JSONValue


__all__ = (
    "NVIDIA_ARCHITECTURE_ROW_FIELD",
    "NvidiaArchitectureReadState",
    "NvidiaArchitectureObservation",
    "NvidiaArchitectureSnapshot",
    "nvidia_architecture_row_observation",
    "read_observed_nvidia_architecture_code",
)

NVIDIA_ARCHITECTURE_ROW_FIELD = "nvidia_architecture"
NVIDIA_ARCHITECTURE_CODE_MAXIMUM = 4294967295


class NvidiaArchitectureReadState(StrEnum):
    OBSERVED = "observed"
    RUNTIME_UNAVAILABLE = "runtime_unavailable"
    QUERY_UNAVAILABLE = "query_unavailable"
    DEVICE_UNAVAILABLE = "device_unavailable"
    IDENTITY_CONFLICT = "identity_conflict"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True, slots=True)
class NvidiaArchitectureObservation:
    device: GPUPhysicalDevice
    state: NvidiaArchitectureReadState
    architecture_code: int | None
    reason_code: str | None = None
    native_identity: GPUPhysicalIdentity | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, NvidiaArchitectureReadState):
            raise ValidationError("NVIDIA architecture read state is invalid.")
        if self.state == NvidiaArchitectureReadState.OBSERVED:
            if self.architecture_code is None or self.native_identity is None:
                raise ValidationError("Observed NVIDIA architecture is missing.")
            require_int_in_range_strict(
                self.architecture_code,
                minimum=0,
                maximum=NVIDIA_ARCHITECTURE_CODE_MAXIMUM,
                error_message="NVIDIA architecture requires a native unsigned 32-bit value.",
            )
        elif self.architecture_code is not None or self.native_identity is not None:
            raise ValidationError("Unobserved NVIDIA architecture cannot carry a native value.")


@dataclass(frozen=True, slots=True)
class NvidiaArchitectureSnapshot:
    physical: GPUPhysicalSnapshot
    observations: tuple[NvidiaArchitectureObservation, ...]


def nvidia_architecture_row_observation(observation: NvidiaArchitectureObservation) -> JSONDict:
    payload: JSONDict = {"state": observation.state.value}
    if observation.architecture_code is not None:
        payload["code"] = observation.architecture_code
    if observation.reason_code is not None:
        payload["reason"] = observation.reason_code
    return payload


def read_observed_nvidia_architecture_code(entry: Mapping[str, JSONValue]) -> int | None:
    observation = entry.get(NVIDIA_ARCHITECTURE_ROW_FIELD)
    if not is_json_dict(observation):
        return None
    if observation.get("state") != NvidiaArchitectureReadState.OBSERVED.value:
        return None
    code = observation.get("code")
    if not is_strict_int(code) or not 0 <= code <= NVIDIA_ARCHITECTURE_CODE_MAXIMUM:
        return None
    return code
