"""SoAI - Fresh Linux DRM and KGSL physical acquisition [backend/hardware/gpu_inventory/linux_platform.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from os import scandir
from os.path import join, realpath, relpath
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_after
from core.errors.exceptions import SoAIError, SoAITimeoutError, StateError, ValidationError
from core.files.directory_descriptor_scope import open_secure_directory_descriptor
from core.filesystem.open_files import open_text
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_physical_identity import GPUInventoryReadState
from hardware.gpu_inventory.drm_physical_observations import parse_drm_uevent
from hardware.gpu_inventory.entries import build_gpu_entry
from hardware.gpu_inventory.kgsl_telemetry import (
    PLATFORM_TELEMETRY_UNAVAILABLE,
    read_kgsl_telemetry,
)
from hardware.gpu_inventory.linux_sysfs_scope import (
    MAX_SYSFS_OBSERVATION_CHARACTERS,
    open_sysfs_device_directory,
    read_sysfs_device_text,
)
from hardware.gpu_inventory.physical_observations import select_gpu_physical_read_state
from hardware.operations import create_device_id
from hardware.vendors.vendor_types import UNKNOWN_VENDOR

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "LinuxPlatformInventory",
    "read_linux_platform_gpu_inventory",
)

_OPERATION = "hardware.gpu_inventory.linux_platform"
_MAX_ENTRIES = 512
_PLATFORM_BUS_TIMEOUT_SECONDS = 3.0
_GPU_DRIVERS = ("vc4-drm", "v3d", "panfrost", "lima", "etnaviv", "kgsl-3d", "kgsl")


@dataclass(frozen=True, slots=True)
class LinuxPlatformInventory:
    gpus: list[JSONDict]
    display_adapters: list[JSONDict]
    pci_drm_slots: tuple[str, ...]
    state: GPUInventoryReadState
    reason_code: str | None
    diagnostics: tuple[SoAIError, ...]


def read_linux_platform_gpu_inventory(*, sysfs_root: str) -> LinuxPlatformInventory:
    root = realpath(sysfs_root)
    diagnostics: list[SoAIError] = []
    gpus: list[JSONDict] = []
    displays: list[JSONDict] = []
    pci_slots: list[str] = []
    identities: dict[str, str] = {}
    observed_devices: set[str] = set()
    states: list[GPUInventoryReadState] = []
    kgsl_present = False
    for interface, pattern in (("drm", r"(?:card\d+|render[D]\d+)"), ("kgsl", r"kgsl-3d\d+")):
        try:
            with scandir(join(root, "class", interface)) as entries:
                nodes = sorted(entry.name for entry in entries)
            if len(nodes) > _MAX_ENTRIES:
                raise ValidationError("Platform GPU class inventory exceeds its bounded scope.")
            if interface == "kgsl":
                kgsl_present = True
        except FileNotFoundError as exception:
            if interface == "kgsl":
                continue
            diagnostics.append(_error("Platform GPU class inventory is unavailable.", exception))
            states.append(GPUInventoryReadState.RUNTIME_UNAVAILABLE)
            continue
        except OSError as exception:
            diagnostics.append(_error("Platform GPU class inventory could not be read.", exception))
            states.append(_failure_state(exception))
            continue
        for locator in nodes:
            if re.fullmatch(pattern, locator) is None:
                continue
            node = join(root, "class", interface, locator)
            try:
                device = realpath(join(node, "device"), strict=True)
                if not device.startswith(f"{join(root, 'devices')}/"):
                    raise ValidationError(
                        "Platform GPU device relation escapes actual sysfs scope."
                    )
                if device in observed_devices:
                    continue
                observed_devices.add(device)
                raw = _read_text(join(device, "uevent"))
                facts = parse_drm_uevent(raw)
                pci = facts.get("PCI_SLOT_NAME")
                if pci is not None:
                    if not normalize_observed_full_pci_bdf(pci):
                        raise ValidationError("DRM PCI device identity is incomplete.")
                    if pci not in pci_slots:
                        pci_slots.append(pci)
                    continue
                driver = facts.get("DRIVER")
                observed_path = facts.get("OF_FULLNAME")
                if observed_path is not None:
                    _require_rooted_path(observed_path)
                    identity = f"linux:of:{observed_path}"
                else:
                    identity = f"linux:sysfs:/{relpath(device, root)}"
                if identity in identities:
                    if identities[identity] != device:
                        raise ValidationError("Platform GPU physical identity is ambiguous.")
                    continue
                compatible = _read_compatible(facts)
                model = _read_text(join(node, "gpu_model")).strip() if interface == "kgsl" else None
                if interface == "kgsl" and not model:
                    raise ValidationError("KGSL actual GPU model response is empty.")
                is_display = driver == "msm_drm"
                known = driver in _GPU_DRIVERS or is_display
                row = _entry(identity, driver, compatible, model, is_display)
                if interface == "kgsl":
                    row.update(read_kgsl_telemetry(node, device))
                if not known:
                    states.append(GPUInventoryReadState.RUNTIME_UNAVAILABLE)
                    diagnostics.append(
                        StateError(
                            "Platform GPU driver coverage is unavailable.",
                            operation=_OPERATION,
                            details={"uevent": raw, "interface": interface},
                        )
                    )
                identities[identity] = device
                (displays if is_display else gpus).append(row)
            except OSError as exception:
                diagnostics.append(
                    _error("Platform GPU device disappeared or cannot be read.", exception)
                )
                states.append(_failure_state(exception))
            except ValidationError as exception:
                diagnostics.append(exception)
                states.append(GPUInventoryReadState.INVALID_RESPONSE)
    reason: str | None = None
    try:
        platform_deadline = deadline_after(_PLATFORM_BUS_TIMEOUT_SECONDS)
        graphics_devices = set(observed_devices)
        with (
            open_secure_directory_descriptor(
                join(root, "bus", "platform", "devices"),
                unsupported_message="Platform GPU descriptor acquisition is unavailable.",
            ) as bus_descriptor,
            scandir(bus_descriptor) as entries,
        ):
            for entry in entries:
                if platform_deadline.expired():
                    raise SoAITimeoutError(
                        "Platform GPU coverage scan exceeded its acquisition deadline."
                    )
                with open_sysfs_device_directory(
                    bus_descriptor, entry.name, devices_root=join(root, "devices")
                ) as (device, descriptor):
                    if device in observed_devices:
                        continue
                    facts = parse_drm_uevent(read_sysfs_device_text(descriptor, "uevent"))
                if (
                    facts.get("DRIVER") in _GPU_DRIVERS
                    or facts.get("DRIVER") == "msm_drm"
                    or facts.get("OF_NAME") in ("gpu", "gpu3d", "qcom,kgsl-3d0", "qcom,mdss_mdp")
                ):
                    graphics_devices.add(device)
                    if len(graphics_devices) > _MAX_ENTRIES:
                        raise ValidationError(
                            "Platform graphics inventory exceeds its bounded scope."
                        )
                    states.append(GPUInventoryReadState.RUNTIME_UNAVAILABLE)
                    diagnostics.append(
                        StateError(
                            "A platform graphics device lacks its actual DRM/KGSL observation.",
                            operation=_OPERATION,
                            details={"uevent": facts},
                        )
                    )
            if platform_deadline.expired():
                raise SoAITimeoutError(
                    "Platform GPU coverage scan exceeded its acquisition deadline."
                )
    except OSError as exception:
        diagnostics.append(_error("Platform device bus coverage is unavailable.", exception))
        states.append(_failure_state(exception))
    except ValidationError as exception:
        diagnostics.append(exception)
        states.append(GPUInventoryReadState.INVALID_RESPONSE)
    except SoAITimeoutError as exception:
        diagnostics.append(exception)
        states.append(GPUInventoryReadState.QUERY_FAILED)
        reason = "platform_acquisition_deadline_expired"
    if displays and not kgsl_present:
        states.append(GPUInventoryReadState.RUNTIME_UNAVAILABLE)
        diagnostics.append(
            StateError(
                "The KGSL compute scope for an observed MSM display is unavailable.",
                operation=_OPERATION,
            )
        )
        if reason is None:
            reason = "kgsl_compute_scope_unavailable"
    state = select_gpu_physical_read_state(states)
    if state != GPUInventoryReadState.OBSERVED and reason is None:
        reason = "platform_physical_scope_unavailable"
    for index, row in enumerate(gpus):
        row["index"] = index
        row["vendor_id"] = index
    for index, row in enumerate(displays):
        row["index"] = index
        row["vendor_id"] = index
    return LinuxPlatformInventory(
        gpus, displays, tuple(pci_slots), state, reason, tuple(diagnostics)
    )


def _read_text(path: str) -> str:
    with open_text(path, encoding="utf-8") as stream:
        value = stream.read(MAX_SYSFS_OBSERVATION_CHARACTERS + 1)
    if len(value) > MAX_SYSFS_OBSERVATION_CHARACTERS:
        raise ValidationError("Platform GPU observation exceeds its bounded input size.")
    return value


def _require_rooted_path(value: str) -> None:
    if (
        not value.startswith("/")
        or "\\" in value
        or "\x00" in value
        or any(part in ("", ".", "..") for part in value.split("/")[1:])
    ):
        raise ValidationError("Platform GPU observed path is invalid.")


def _read_compatible(facts: dict[str, str]) -> tuple[str, ...]:
    indexed = {
        key: value for key, value in facts.items() if re.fullmatch(r"OF_COMPATIBLE_\d+", key)
    }
    count = facts.get("OF_COMPATIBLE_N")
    if count is None:
        if indexed:
            raise ValidationError("Platform GPU compatible list lacks actual count authority.")
        return ()
    if (
        not count.isdecimal()
        or int(count) > _MAX_ENTRIES
        or set(indexed) != {f"OF_COMPATIBLE_{index}" for index in range(int(count))}
    ):
        raise ValidationError("Platform GPU compatible observations are incomplete.")
    return tuple(indexed[f"OF_COMPATIBLE_{index}"] for index in range(int(count)))


def _entry(
    identity: str,
    driver: str | None,
    compatible: tuple[str, ...],
    model: str | None,
    is_display: bool,
) -> JSONDict:
    row = build_gpu_entry(
        vendor=UNKNOWN_VENDOR,
        index=0,
        vendor_id=None,
        device_id=create_device_id(
            "gpu", f"linux-native-{sha256(identity.encode('utf-8')).hexdigest()}"
        ),
        name=model or driver or "Platform GPU",
        memory_used_mb=0,
        memory_total_mb=0,
        percent_used=0.0,
    )
    row.update(
        {
            "native_device_path": identity,
            "platform_driver": driver,
            "platform_compatible": list(compatible),
            "compute_capable": False if is_display else True if driver in _GPU_DRIVERS else None,
            "display_adapter_type": "platform_display" if is_display else None,
            "telemetry_available": False,
            "telemetry_unavailable_reason": PLATFORM_TELEMETRY_UNAVAILABLE,
            "memory_used_mb": None,
            "memory_total_mb": None,
            "percent_used": None,
            "memory_type": "shared",
        }
    )
    return row


def _failure_state(exception: OSError) -> GPUInventoryReadState:
    if isinstance(exception, PermissionError):
        return GPUInventoryReadState.PERMISSION_DENIED
    if isinstance(exception, FileNotFoundError):
        return GPUInventoryReadState.RUNTIME_UNAVAILABLE
    return GPUInventoryReadState.QUERY_FAILED


def _error(message: str, exception: OSError) -> StateError:
    return StateError(message, operation=_OPERATION, cause=exception)
