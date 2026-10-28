"""SoAI - Consistent observed compute driver versions [backend/core/hardware/compute_driver_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.meta.versioning import NormalizedVersion, parse_semantic_version
from core.types.json import JSONValue

__all__ = ("ComputeDriverObservation", "read_compute_driver_observation")


@dataclass(frozen=True, slots=True)
class ComputeDriverObservation:
    family_present: bool
    version: NormalizedVersion | None = None
    reported_version: str | None = None


def read_compute_driver_observation(
    compute_drivers: Mapping[str, JSONValue], family: str
) -> ComputeDriverObservation:
    matches = [
        payload
        for name, payload in compute_drivers.items()
        if name.strip().casefold() == family.strip().casefold()
    ]
    if not matches:
        return ComputeDriverObservation(False)
    observed: NormalizedVersion | None = None
    for payload in matches:
        if not isinstance(payload, Mapping):
            return ComputeDriverObservation(True)
        version = payload.get("version")
        if not isinstance(version, str) or not version.strip():
            return ComputeDriverObservation(True)
        try:
            candidate = parse_semantic_version(version)
        except ValidationError:
            return ComputeDriverObservation(
                True, reported_version=version.strip() if len(matches) == 1 else None
            )
        if observed is not None and candidate != observed:
            return ComputeDriverObservation(True)
        observed = candidate
    return ComputeDriverObservation(True, observed, str(observed) if observed is not None else None)
