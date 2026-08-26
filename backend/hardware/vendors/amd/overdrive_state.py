"""SoAI - AMDGPU OverDrive sysfs state parsing [backend/hardware/vendors/amd/overdrive_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.filesystem.text_read import read_text_if_exists
from core.validation.coercion import coerce_int_from_scalar
from hardware.gpu_inventory.identity import normalize_pci_bdf

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "AMDGPU_OVERDRIVE_BACKEND",
    "AmdgpuOverdrivePaths",
    "build_amdgpu_overdrive_capabilities",
    "resolve_amdgpu_overdrive_paths",
)

AMDGPU_OVERDRIVE_BACKEND = "amd_overdrive"
CLOCK_LINE_PATTERN = r"^(?P<level>[0-9]+):\s*(?P<value>-?[0-9]+)\s*M[Hh]z$"
RANGE_LINE_PATTERN = (
    r"^(?P<name>SCLK|MCLK):\s*(?P<minimum>-?[0-9]+)\s*M[Hh]z\s+(?P<maximum>-?[0-9]+)\s*M[Hh]z$"
)


@dataclass(frozen=True, slots=True)
class AmdgpuOverdrivePaths:
    device_dir: str
    overdrive_path: str
    performance_level_path: str


@dataclass(frozen=True, slots=True)
class AmdgpuOverdriveState:
    sclk_levels: dict[int, int]
    mclk_levels: dict[int, int]
    ranges: dict[str, tuple[int, int]]


def resolve_amdgpu_overdrive_paths(pci_bdf: str | None) -> AmdgpuOverdrivePaths | None:
    normalized_bdf = normalize_pci_bdf(pci_bdf) if isinstance(pci_bdf, str) else ""
    if not normalized_bdf:
        return None
    try:
        sys_drm_path = _sys_drm_path()
        card_names = sorted(os.listdir(sys_drm_path))
    except OSError:
        return None
    for card_name in card_names:
        if not card_name.startswith("card"):
            continue
        device_dir = os.path.join(sys_drm_path, card_name, "device")
        uevent_text = read_text_if_exists(os.path.join(device_dir, "uevent"))
        if uevent_text is None or normalized_bdf != _extract_uevent_pci_slot_bdf(uevent_text):
            continue
        overdrive_path = os.path.join(device_dir, "pp_od_clk_voltage")
        performance_level_path = os.path.join(device_dir, "power_dpm_force_performance_level")
        if os.path.exists(overdrive_path):
            return AmdgpuOverdrivePaths(
                device_dir=device_dir,
                overdrive_path=overdrive_path,
                performance_level_path=performance_level_path,
            )
    return None


def _extract_uevent_pci_slot_bdf(uevent_text: str) -> str:
    for raw_line in uevent_text.splitlines():
        key, separator, value = raw_line.partition("=")
        if key == "PCI_SLOT_NAME" and separator:
            return normalize_pci_bdf(value)
    return ""


def _sys_drm_path() -> str:
    return os.path.join(os.sep, "sys", "class", "drm")


def build_amdgpu_overdrive_capabilities(pci_bdf: str | None) -> JSONDict | None:
    paths = resolve_amdgpu_overdrive_paths(pci_bdf)
    if paths is None:
        return None
    state = _read_overdrive_state(paths.overdrive_path)
    if state is None:
        return None
    capabilities: JSONDict = {
        "overdrive_pci_bdf": normalize_pci_bdf(pci_bdf) if isinstance(pci_bdf, str) else None,
    }
    core_caps = _clock_capability(state.sclk_levels, state.ranges.get("SCLK"))
    if core_caps is not None:
        capabilities["core_clock_mhz"] = core_caps
    mem_caps = _clock_capability(state.mclk_levels, state.ranges.get("MCLK"))
    if mem_caps is not None:
        capabilities["mem_clock_mhz"] = mem_caps
    return capabilities


def _read_overdrive_state(path: str) -> AmdgpuOverdriveState | None:
    text = read_text_if_exists(path)
    if text is None:
        return None
    section = ""
    sclk_levels: dict[int, int] = {}
    mclk_levels: dict[int, int] = {}
    ranges: dict[str, tuple[int, int]] = {}
    for raw_line in text.replace("\x00", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in {"OD_SCLK:", "OD_MCLK:", "OD_RANGE:"}:
            section = line.rstrip(":")
            continue
        if section == "OD_SCLK":
            _parse_clock_line(line, sclk_levels)
        elif section == "OD_MCLK":
            _parse_clock_line(line, mclk_levels)
        elif section == "OD_RANGE":
            _parse_range_line(line, ranges)
    return AmdgpuOverdriveState(
        sclk_levels=sclk_levels,
        mclk_levels=mclk_levels,
        ranges=ranges,
    )


def _parse_clock_line(line: str, levels: dict[int, int]) -> None:
    match = re.match(CLOCK_LINE_PATTERN, line)
    if match is None:
        return
    level = coerce_int_from_scalar(match.group("level"))
    value = coerce_int_from_scalar(match.group("value"))
    if level is not None and value is not None:
        levels[level] = value


def _parse_range_line(line: str, ranges: dict[str, tuple[int, int]]) -> None:
    match = re.match(RANGE_LINE_PATTERN, line)
    if match is None:
        return
    minimum = coerce_int_from_scalar(match.group("minimum"))
    maximum = coerce_int_from_scalar(match.group("maximum"))
    if minimum is not None and maximum is not None and minimum < maximum:
        ranges[match.group("name")] = (minimum, maximum)


def _clock_capability(
    levels: dict[int, int], value_range: tuple[int, int] | None
) -> JSONDict | None:
    if value_range is None or not levels:
        return None
    high_level = max(levels)
    current = levels.get(high_level)
    if current is None:
        return None
    minimum, maximum = value_range
    return {
        "supported": True,
        "min": minimum,
        "max": maximum,
        "default": current,
        "current": current,
        "step": 1,
        "requires_admin": True,
        "control_backend": AMDGPU_OVERDRIVE_BACKEND,
        "auto_requires_apply": True,
        "levels": [
            {"level": level, "mhz": value}
            for level, value in sorted(levels.items(), key=lambda item: item[0])
        ],
    }
