"""SoAI - AMDGPU OverDrive sysfs state parsing [backend/hardware/vendors/amd/overdrive_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import open_text
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_physical_identity import GPUInventoryReadState
from hardware.gpu_inventory.identity import normalize_pci_bdf
from hardware.vendors.amd.overdrive_observations import parse_amd_overdrive_observation

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "AMDGPU_OVERDRIVE_BACKEND",
    "AmdgpuOverdrivePaths",
    "AmdgpuOverdriveProbeResult",
    "build_amdgpu_overdrive_capabilities",
    "resolve_amdgpu_overdrive_paths",
)

AMDGPU_OVERDRIVE_BACKEND = "amd_overdrive"


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


@dataclass(frozen=True, slots=True)
class AmdgpuOverdriveProbeResult:
    state: GPUInventoryReadState
    reason_code: str | None
    payload: JSONDict | None
    failure: Exception | None


def resolve_amdgpu_overdrive_paths(pci_bdf: str | None) -> AmdgpuOverdrivePaths | None:
    normalized_bdf = normalize_observed_full_pci_bdf(pci_bdf) if isinstance(pci_bdf, str) else None
    if not normalized_bdf:
        return None
    try:
        sys_drm_path = _sys_drm_path()
        card_names = sorted(os.listdir(sys_drm_path))
    except FileNotFoundError:
        return None
    candidates: list[AmdgpuOverdrivePaths] = []
    for card_name in card_names:
        if not card_name.startswith("card"):
            continue
        device_dir = os.path.join(sys_drm_path, card_name, "device")
        try:
            with open_text(os.path.join(device_dir, "uevent"), encoding="utf-8") as handle:
                uevent_text = handle.read()
        except FileNotFoundError:
            continue
        identity: dict[str, str] = {}
        for line in uevent_text.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                if key in identity:
                    raise ValidationError(
                        "AMDGPU sysfs physical identity contains duplicate fields."
                    )
                identity[key] = value
        if normalized_bdf != normalize_observed_full_pci_bdf(identity.get("PCI_SLOT_NAME", "")):
            continue
        if identity.get("PCI_ID", "").split(":")[0].casefold() != "1002":
            continue
        overdrive_path = os.path.join(device_dir, "pp_od_clk_voltage")
        performance_level_path = os.path.join(device_dir, "power_dpm_force_performance_level")
        if os.path.exists(overdrive_path):
            candidates.append(
                AmdgpuOverdrivePaths(
                    device_dir=device_dir,
                    overdrive_path=overdrive_path,
                    performance_level_path=performance_level_path,
                )
            )
    if len(candidates) > 1:
        raise StateError("AMDGPU OverDrive physical device relationship is ambiguous.")
    return candidates[0] if candidates else None


def _sys_drm_path() -> str:
    return os.path.join(os.sep, "sys", "class", "drm")


def build_amdgpu_overdrive_capabilities(pci_bdf: str | None) -> AmdgpuOverdriveProbeResult:
    try:
        paths = resolve_amdgpu_overdrive_paths(pci_bdf)
        if paths is None:
            return AmdgpuOverdriveProbeResult(
                GPUInventoryReadState.RUNTIME_UNAVAILABLE, "overdrive_unavailable", None, None
            )
        with open_text(paths.overdrive_path, encoding="utf-8") as handle:
            output = handle.read()
        if not output.strip():
            raise ValidationError("AMDGPU OverDrive returned empty native state.")
        observed = parse_amd_overdrive_observation(output, paths.overdrive_path)
        state = AmdgpuOverdriveState(
            dict(observed.sclk_levels),
            dict(observed.mclk_levels),
            {name: (minimum, maximum) for name, minimum, maximum in observed.ranges},
        )
    except FileNotFoundError as exception:
        return AmdgpuOverdriveProbeResult(
            GPUInventoryReadState.RUNTIME_UNAVAILABLE, "device_disappeared", None, exception
        )
    except OSError as exception:
        return AmdgpuOverdriveProbeResult(
            GPUInventoryReadState.QUERY_FAILED,
            (
                "permission_denied"
                if isinstance(exception, PermissionError)
                else "overdrive_query_failed"
            ),
            None,
            exception,
        )
    except (StateError, ValidationError) as exception:
        return AmdgpuOverdriveProbeResult(
            GPUInventoryReadState.INVALID_RESPONSE, "overdrive_invalid", None, exception
        )
    capabilities: JSONDict = {
        "overdrive_pci_bdf": normalize_pci_bdf(pci_bdf) if isinstance(pci_bdf, str) else None,
        "pci_bdf_full": pci_bdf,
        "pci_bdf_observations": [pci_bdf],
    }
    core_caps = _clock_capability(
        state.sclk_levels,
        state.ranges.get("SCLK"),
        numeric_supported=not observed.additional_rows and max(state.sclk_levels, default=-1) == 1,
    )
    if core_caps is not None:
        capabilities["core_clock_mhz"] = core_caps
    mem_caps = _clock_capability(
        state.mclk_levels, state.ranges.get("MCLK"), numeric_supported=False
    )
    if mem_caps is not None:
        capabilities["mem_clock_mhz"] = mem_caps
    return AmdgpuOverdriveProbeResult(GPUInventoryReadState.OBSERVED, None, capabilities, None)


def _clock_capability(
    levels: dict[int, int], value_range: tuple[int, int] | None, *, numeric_supported: bool
) -> JSONDict | None:
    if value_range is None or not levels:
        return None
    high_level = max(levels)
    current = levels.get(high_level)
    if current is None:
        return None
    minimum, maximum = value_range
    return {
        "supported": numeric_supported,
        "numeric_supported": numeric_supported,
        "auto_supported": False,
        "min": minimum,
        "max": maximum,
        "default": None,
        "current": current,
        "step": 1,
        "requires_admin": True,
        "control_backend": AMDGPU_OVERDRIVE_BACKEND if numeric_supported else None,
        "unsupported_reason": None if numeric_supported else "native_control_unavailable",
        "auto_requires_apply": True,
        "levels": [
            {"level": level, "mhz": value}
            for level, value in sorted(levels.items(), key=lambda item: item[0])
        ],
    }
