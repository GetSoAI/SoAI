"""SoAI - Bounded Vulkan physical device acquisition [backend/plugin_sdk/contracts/accelerator_vulkan_acquisition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

from core.concurrency.deadlines import deadline_after
from core.errors.exceptions import ConfigurationError
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingState,
    compare_gpu_physical_identities,
)
from core.hardware.vulkan_physical_probe import run_vulkan_physical_probe
from core.system.commands import run_argv_capture
from core.types.json import JSONDict
from core.validation.integers import is_non_negative_strict_int
from plugin_sdk.contracts.accelerator_device_identity import normalize_accelerator_hex_id
from plugin_sdk.contracts.accelerator_vulkan_devices import (
    VULKAN_ACQUISITION_TIMEOUT_SECONDS,
    VulkanBindingFailure,
    VulkanPhysicalDevice,
    parse_vulkan_text_devices,
    vulkan_binding_error,
)

__all__ = (
    "VulkanDeviceAcquisition",
    "enrich_vulkan_devices",
    "native_vulkan_device",
)

SUMMARY_COMMAND = ("vulkaninfo", "--summary")
FULL_COMMAND = ("vulkaninfo",)
_QUERY_FAILURE_PRIORITY = (
    VulkanBindingFailure.QUERY_TIMEOUT,
    VulkanBindingFailure.FORMAT_UNSUPPORTED,
    VulkanBindingFailure.RUNTIME_UNAVAILABLE,
)


class VulkanDeviceAcquisition:
    def __init__(self) -> None:
        self._deadline = deadline_after(VULKAN_ACQUISITION_TIMEOUT_SECONDS)
        self._failures: set[VulkanBindingFailure] = set()
        self._full_observed = False
        self._native_acquired = False
        self._native_devices: list[VulkanPhysicalDevice] | None = None

    def rosters(self) -> Iterator[list[VulkanPhysicalDevice]]:
        for command in (SUMMARY_COMMAND, FULL_COMMAND):
            devices = self._query(command)
            if devices is None:
                continue
            self._full_observed = command == FULL_COMMAND
            yield devices
            enriched = enrich_vulkan_devices(devices, self._native())
            if enriched != devices:
                yield enriched

    def failure(self, unresolved: ConfigurationError | None) -> ConfigurationError:
        if unresolved is not None and self._full_observed:
            return unresolved
        for failure in _QUERY_FAILURE_PRIORITY:
            if failure in self._failures:
                return vulkan_binding_error(failure)
        return unresolved or vulkan_binding_error(VulkanBindingFailure.RUNTIME_UNAVAILABLE)

    def _remaining_timeout(self) -> int | None:
        remaining_seconds = int(self._deadline.remaining_seconds())
        return remaining_seconds if remaining_seconds >= 1 else None

    def _query(self, command: tuple[str, ...]) -> list[VulkanPhysicalDevice] | None:
        timeout = self._remaining_timeout()
        if timeout is None:
            self._failures.add(VulkanBindingFailure.QUERY_TIMEOUT)
            return None
        result = run_argv_capture(list(command), timeout=timeout)
        if result.timed_out:
            self._failures.add(VulkanBindingFailure.QUERY_TIMEOUT)
            return None
        if result.return_code != 0 or not result.stdout.strip():
            self._failures.add(VulkanBindingFailure.RUNTIME_UNAVAILABLE)
            return None
        devices = parse_vulkan_text_devices(result.stdout)
        if devices is None:
            self._failures.add(VulkanBindingFailure.FORMAT_UNSUPPORTED)
        return devices

    def _native(self) -> list[VulkanPhysicalDevice] | None:
        if self._native_acquired:
            return self._native_devices
        self._native_acquired = True
        timeout = self._remaining_timeout()
        observations = run_vulkan_physical_probe(timeout) if timeout is not None else None
        if observations is None:
            return None
        devices: list[VulkanPhysicalDevice] = []
        for observation in observations:
            device = native_vulkan_device(observation)
            if device is None or any(retained.index == device.index for retained in devices):
                return None
            devices.append(device)
        self._native_devices = devices
        return devices


def native_vulkan_device(observation: JSONDict) -> VulkanPhysicalDevice | None:
    index = observation.get("vulkan_index")
    uuid = observation.get("uuid")
    pci_bdf_full = observation.get("pci_bdf_full")
    vendor_id = normalize_accelerator_hex_id(observation.get("pci_vendor_id"))
    device_id = normalize_accelerator_hex_id(observation.get("pci_device_id"))
    if not is_non_negative_strict_int(index) or vendor_id is None or device_id is None:
        return None
    if uuid is not None and (not isinstance(uuid, str) or not uuid):
        return None
    if pci_bdf_full is not None and (
        not isinstance(pci_bdf_full, str) or not normalize_observed_full_pci_bdf(pci_bdf_full)
    ):
        return None
    return VulkanPhysicalDevice(
        index=index,
        name_key=None,
        vendor_id=vendor_id,
        device_id=device_id,
        uuid=uuid,
        pci_bdf_full=pci_bdf_full,
    )


def enrich_vulkan_devices(
    devices: list[VulkanPhysicalDevice], native_devices: list[VulkanPhysicalDevice] | None
) -> list[VulkanPhysicalDevice]:
    if native_devices is None:
        return devices
    native_by_index = {device.index: device for device in native_devices}
    if set(native_by_index) != {device.index for device in devices}:
        return devices
    enriched: list[VulkanPhysicalDevice] = []
    for device in devices:
        native = native_by_index[device.index]
        relation = _identity_relation(device, native)
        if device.vendor_device_key() != native.vendor_device_key() or relation not in (
            GPUPhysicalBindingState.BOUND,
            GPUPhysicalBindingState.IDENTITY_UNAVAILABLE,
        ):
            return devices
        enriched.append(
            replace(device, pci_bdf_full=native.pci_bdf_full)
            if relation == GPUPhysicalBindingState.BOUND and device.pci_bdf_full is None
            else device
        )
    return enriched


def _identity_relation(
    device: VulkanPhysicalDevice, native: VulkanPhysicalDevice
) -> GPUPhysicalBindingState:
    identity = device.physical_identity()
    native_identity = native.physical_identity()
    if identity is None or native_identity is None:
        return GPUPhysicalBindingState.IDENTITY_UNAVAILABLE
    return compare_gpu_physical_identities(identity, native_identity)
