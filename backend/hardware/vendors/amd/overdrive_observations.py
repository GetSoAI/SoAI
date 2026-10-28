"""SoAI - Complete AMD configured clock domains and mutable native table grammar [backend/hardware/vendors/amd/overdrive_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass

from core.errors.exceptions import ValidationError

__all__ = (
    "AmdOverdriveObservation",
    "parse_amd_overdrive_observation",
)


@dataclass(frozen=True, slots=True)
class AmdOverdriveObservation:
    sclk_levels: tuple[tuple[int, int], ...]
    mclk_levels: tuple[tuple[int, int], ...]
    ranges: tuple[tuple[str, int, int], ...]
    additional_rows: tuple[str, ...]
    path: str


def parse_amd_overdrive_observation(output: str, path: str) -> AmdOverdriveObservation:
    clocks: dict[str, dict[int, int]] = {"OD_SCLK": {}, "OD_MCLK": {}}
    ranges: dict[str, tuple[int, int]] = {}
    additional: list[str] = []
    section = ""
    for raw in output.replace("\0", "\n").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.endswith(":"):
            section = line.removesuffix(":")
            if section not in (*clocks, "OD_RANGE"):
                additional.append(line)
            continue
        if section in clocks:
            match = re.fullmatch(r"(\d+):\s*(\d+)\s*M[Hh]z", line)
            if match is None:
                additional.append(line)
                continue
            index, value = int(match[1]), int(match[2])
            if index in clocks[section] or value <= 0:
                raise ValidationError("AMD actual clock member is duplicated or invalid.")
            clocks[section][index] = value
        elif section == "OD_RANGE":
            match = re.fullmatch(r"(SCLK|MCLK):\s*(\d+)\s*M[Hh]z\s+(\d+)\s*M[Hh]z", line)
            if match is None:
                additional.append(line)
                continue
            field, minimum, maximum = match[1], int(match[2]), int(match[3])
            if field in ranges or not 0 < minimum <= maximum:
                raise ValidationError("AMD actual clock range is duplicated or invalid.")
            ranges[field] = minimum, maximum
        else:
            additional.append(line)
    return AmdOverdriveObservation(
        tuple(sorted(clocks["OD_SCLK"].items())),
        tuple(sorted(clocks["OD_MCLK"].items())),
        tuple((name, *limits) for name, limits in sorted(ranges.items())),
        tuple(additional),
        path,
    )
