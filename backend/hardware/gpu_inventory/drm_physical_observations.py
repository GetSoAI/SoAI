"""SoAI - Strict DRM uevent and primary-node observations [backend/hardware/gpu_inventory/drm_physical_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import open_text

__all__ = ("parse_drm_uevent", "read_drm_primary_node")


def parse_drm_uevent(raw: str) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in raw.splitlines():
        key, separator, value = line.partition("=")
        if not separator or not key or key in facts or not value or value != value.strip():
            raise ValidationError("DRM uevent grammar is invalid.", details={"raw_uevent": raw})
        facts[key] = value
    if not facts:
        raise ValidationError("DRM uevent response is empty.")
    return facts


def read_drm_primary_node(device_directory: str) -> tuple[str, tuple[int, int]]:
    candidates: list[tuple[str, tuple[int, int]]] = []
    directory = os.path.join(device_directory, "drm")
    for name in os.listdir(directory):
        if not name.startswith("card") or not name[4:].isdigit():
            continue
        with open_text(os.path.join(directory, name, "dev"), encoding="ascii") as handle:
            numbers = handle.read(64).strip().split(":")
        if len(numbers) != 2 or not all(number.isdigit() for number in numbers):
            raise ValidationError("DRM primary device number is invalid.")
        candidates.append((name, (int(numbers[0]), int(numbers[1]))))
    if len(candidates) != 1:
        raise StateError("DRM primary physical node is unavailable or ambiguous.")
    return candidates[0]
