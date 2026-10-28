"""SoAI - Observed GPU physical identity contracts [backend/core/hardware/gpu_physical_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_identity_normalization import (
    normalize_observed_full_pci_bdf,
    normalize_windows_pnp_instance_id,
    observed_pci_bdf_components,
    observed_pci_bdf_conflicts,
)
from core.types.json import JSONDict
from core.validation.strings import require_canonical_trimmed_json_text

if TYPE_CHECKING:
    from uuid import UUID

__all__ = (
    "GPUInventoryReadState",
    "GPUPhysicalIdentity",
    "GPUPhysicalDevice",
    "GPUVendorObservation",
    "GPUPhysicalSnapshot",
    "GPUPhysicalBindingState",
    "GPUPhysicalBindingResult",
    "NVIDIA_PCI_VENDOR_ID",
    "compare_gpu_physical_identities",
    "gpu_physical_device_observations",
    "vulkan_device_uuid_identity",
)

NVIDIA_PCI_VENDOR_ID = 0x10DE


class GPUInventoryReadState(StrEnum):
    OBSERVED = "observed"
    RUNTIME_UNAVAILABLE = "runtime_unavailable"
    QUERY_FAILED = "query_failed"
    PERMISSION_DENIED = "permission_denied"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True, slots=True)
class GPUPhysicalIdentity:
    uuid: str | None
    pci_bdf_full: str | None
    native_device_path: str | None = None
    windows_pnp_instance_id: str | None = None

    def __post_init__(self) -> None:
        if all(
            value is None
            for value in (
                self.uuid,
                self.pci_bdf_full,
                self.native_device_path,
                self.windows_pnp_instance_id,
            )
        ):
            raise ValidationError("GPU physical identity is unavailable.")
        if self.uuid is not None:
            require_canonical_trimmed_json_text(
                self.uuid, error_message="GPU UUID must be nonempty canonical text."
            )
        if self.pci_bdf_full is not None and not normalize_observed_full_pci_bdf(self.pci_bdf_full):
            raise ValidationError("GPU PCI identity requires an observed domain and function.")
        if self.native_device_path is not None:
            require_canonical_trimmed_json_text(
                self.native_device_path, error_message="GPU native device path is invalid."
            )
            prefixes = ("linux:of:/", "linux:sysfs:/devices/", "darwin:ioreg:IOService:/")
            prefix = next(
                (value for value in prefixes if self.native_device_path.startswith(value)), None
            )
            if (
                prefix is None
                or "\\" in self.native_device_path
                or "\x00" in self.native_device_path
                or any(
                    part in ("", ".", "..")
                    for part in self.native_device_path[len(prefix) :].split("/")
                )
            ):
                raise ValidationError(
                    "GPU native device path lacks actual rooted namespace authority."
                )

        if self.windows_pnp_instance_id is not None and (
            not isinstance(self.windows_pnp_instance_id, str)
            or not self.windows_pnp_instance_id
            or normalize_windows_pnp_instance_id(self.windows_pnp_instance_id)
            != self.windows_pnp_instance_id
        ):
            raise ValidationError(
                "GPU Windows PNP identity requires a canonical full PCI instance ID."
            )

    def validate_observations(self, observations: tuple[str, ...]) -> None:
        if not isinstance(observations, tuple):
            raise ValidationError("GPU actual PCI observations require an immutable tuple.")
        previous = [self.pci_bdf_full] if self.pci_bdf_full is not None else []
        for observation in observations:
            if not isinstance(observation, str) or observed_pci_bdf_components(observation) is None:
                raise ValidationError("GPU actual PCI observation is invalid.")
            if any(observed_pci_bdf_conflicts(observation, value) for value in previous):
                raise ValidationError("GPU actual PCI observations conflict.")
            previous.append(observation)


@dataclass(frozen=True, slots=True)
class GPUPhysicalDevice:
    device_id: str
    vendor: str
    identity: GPUPhysicalIdentity
    gpu_index: int | None
    vendor_index: int | None
    pci_bdf_observations: tuple[str, ...]
    platform_driver: str | None = None
    platform_compatible: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_canonical_trimmed_json_text(
            self.device_id, error_message="GPU physical device identifier is invalid."
        )
        require_canonical_trimmed_json_text(
            self.vendor, error_message="GPU physical vendor is invalid."
        )
        if not isinstance(self.identity, GPUPhysicalIdentity):
            raise ValidationError("GPU physical identity is invalid.")
        self.identity.validate_observations(self.pci_bdf_observations)
        if self.platform_driver is not None:
            require_canonical_trimmed_json_text(
                self.platform_driver, error_message="GPU observed platform driver is invalid."
            )
        if not isinstance(self.platform_compatible, tuple):
            raise ValidationError("GPU actual compatible observations require an immutable tuple.")
        for compatible in self.platform_compatible:
            require_canonical_trimmed_json_text(
                compatible, error_message="GPU observed platform compatibility is invalid."
            )


def gpu_physical_device_observations(device: GPUPhysicalDevice) -> JSONDict:
    return {
        "device_id": device.device_id,
        "type": device.vendor,
        "uuid": device.identity.uuid,
        "pci_bdf_full": device.identity.pci_bdf_full,
        "windows_pnp_instance_id": device.identity.windows_pnp_instance_id,
        "native_device_path": device.identity.native_device_path,
        "platform_driver": device.platform_driver,
        "platform_compatible": list(device.platform_compatible),
        "pci_bdf_observations": list(device.pci_bdf_observations),
        "index": device.gpu_index,
        "vendor_id": device.vendor_index,
    }


@dataclass(frozen=True, slots=True)
class GPUVendorObservation:
    vendor: str
    state: GPUInventoryReadState
    reason_code: str | None


@dataclass(frozen=True, slots=True)
class GPUPhysicalSnapshot:
    acquisition_id: str
    devices: tuple[GPUPhysicalDevice, ...]
    vendors: tuple[GPUVendorObservation, ...]


class GPUPhysicalBindingState(StrEnum):
    BOUND = "bound"
    DEVICE_UNAVAILABLE = "device_unavailable"
    IDENTITY_UNAVAILABLE = "identity_unavailable"
    IDENTITY_CONFLICT = "identity_conflict"
    QUERY_UNAVAILABLE = "query_unavailable"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True, slots=True)
class GPUPhysicalBindingResult:
    state: GPUPhysicalBindingState
    device: GPUPhysicalDevice | None
    reason_code: str | None


def compare_gpu_physical_identities(
    selected: GPUPhysicalIdentity, candidate: GPUPhysicalIdentity
) -> GPUPhysicalBindingState:
    agreements: list[bool] = []
    if selected.native_device_path is not None and candidate.native_device_path is not None:
        agreements.append(selected.native_device_path == candidate.native_device_path)
    if selected.uuid is not None and candidate.uuid is not None:
        agreements.append(selected.uuid.casefold() == candidate.uuid.casefold())
    if selected.pci_bdf_full is not None and candidate.pci_bdf_full is not None:
        agreements.append(
            normalize_observed_full_pci_bdf(selected.pci_bdf_full)
            == normalize_observed_full_pci_bdf(candidate.pci_bdf_full)
        )
    if (
        selected.windows_pnp_instance_id is not None
        and candidate.windows_pnp_instance_id is not None
    ):
        agreements.append(selected.windows_pnp_instance_id == candidate.windows_pnp_instance_id)
    if not agreements:
        return GPUPhysicalBindingState.IDENTITY_UNAVAILABLE
    if not any(agreements):
        return GPUPhysicalBindingState.DEVICE_UNAVAILABLE
    if not all(agreements):
        return GPUPhysicalBindingState.IDENTITY_CONFLICT
    return GPUPhysicalBindingState.BOUND


def vulkan_device_uuid_identity(vendor_id: int, device_uuid: UUID) -> str | None:
    if device_uuid.int == 0:
        return None
    return f"GPU-{device_uuid}" if vendor_id == NVIDIA_PCI_VENDOR_ID else str(device_uuid)
