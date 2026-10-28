"""SoAI - GPU device ID resolution [backend/hardware/manager/gpu_device_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.hardware.gpu_inventory_errors import GPUInventoryBusyError
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState, GPUPhysicalDevice
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.system.protocols import CommandExecutorProtocol
from core.timing.epoch import epoch_ms
from core.validation.strict_integer import is_strict_int
from hardware.gpu_info_resolution import get_gpu_observation_for_services
from hardware.gpu_inventory.identity import normalize_identity_index
from hardware.gpu_inventory.physical_binding import (
    match_gpu_physical_identity,
    resolve_gpu_physical_binding,
)
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)
from hardware.vendors.amd.adl_session import AdlRuntime

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from hardware.internal_protocols import GPUInfoObservation

__all__ = ("resolve_gpu_device_id",)


@dataclass(frozen=True, slots=True)
class GPUHistoryDeviceResolution:
    device: GPUPhysicalDevice
    observed_at_ms: int | None
    stale: bool
    inventory_revision: int

    def metadata(self) -> JSONDict:
        checked_at_ms = epoch_ms()
        return {
            "status": "stale" if self.stale else "available",
            "observed_at_ms": self.observed_at_ms,
            "checked_at_ms": checked_at_ms,
            "age_ms": (
                max(0, checked_at_ms - self.observed_at_ms)
                if self.observed_at_ms is not None
                else None
            ),
            "sampled_current": False,
            "inventory_revision": self.inventory_revision,
        }


def resolve_gpu_device_id(
    gpu_index: int,
    executor: CommandExecutorProtocol,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    adl_runtime: AdlRuntime | None = None,
) -> GPUHistoryDeviceResolution | None:
    if not is_strict_int(gpu_index) or gpu_index < 0:
        return None
    stale = False
    retained_observations: tuple[GPUInfoObservation, ...] = ()
    revision = gpu_info_cache_service.revision()
    try:
        observation = get_gpu_observation_for_services(
            executor,
            detailed=False,
            gpu_info_cache_service=gpu_info_cache_service,
            gpu_vendor_detection_service=gpu_vendor_detection_service,
            nvidia_nvml_gate=nvidia_nvml_gate,
            nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
            adl_runtime=adl_runtime,
        )
        stale = observation.refresh_failed
    except TimeoutError as exception:
        with gpu_info_cache_service.lock:
            if revision != gpu_info_cache_service.revision():
                raise GPUInventoryBusyError(
                    "GPU history observation revision changed.", cause=exception
                ) from exception
            retained_observations = gpu_info_cache_service.get_retained_observations()
            retained = retained_observations[0] if retained_observations else None
        if retained is None:
            raise GPUInventoryBusyError(
                "GPU history has no retained physical mapping.", cause=exception
            ) from exception
        observation = retained
        stale = True
    if stale and not retained_observations:
        with gpu_info_cache_service.lock:
            retained_observations = gpu_info_cache_service.get_retained_observations()
    gpu_snapshot = observation.payload
    gpus_value: JSONValue | None = gpu_snapshot.get("gpus")
    if not isinstance(gpus_value, list) or not gpus_value:
        if stale:
            raise GPUInventoryBusyError("GPU history has no retained physical mapping.")
        return None
    gpus: list[JSONDict] = [entry for entry in gpus_value if isinstance(entry, dict)]
    matches = [entry for entry in gpus if normalize_identity_index(entry.get("index")) == gpu_index]
    if len(matches) != 1:
        if stale:
            raise GPUInventoryBusyError("GPU history retained index is unavailable or ambiguous.")
        return None
    binding = resolve_gpu_physical_binding(matches[0], gpus)
    for retained_observation in retained_observations:
        peers = retained_observation.payload.get("gpus")
        if not isinstance(peers, list):
            raise GPUInventoryBusyError("GPU history retained roster is malformed.")
        peer_roster = [peer for peer in peers if isinstance(peer, dict)]
        peer_binding = resolve_gpu_physical_binding(matches[0], peer_roster)
        peer_matches = [
            peer for peer in peer_roster if normalize_identity_index(peer.get("index")) == gpu_index
        ]
        if peer_binding.state != GPUPhysicalBindingState.BOUND or len(peer_matches) != 1:
            raise GPUInventoryBusyError("GPU history retained roster is not uniquely bound.")
        for peer in peers:
            if not isinstance(peer, dict):
                continue
            same_index = normalize_identity_index(peer.get("index")) == gpu_index
            relation = match_gpu_physical_identity(matches[0], peer)
            if relation == GPUPhysicalBindingState.IDENTITY_CONFLICT or (
                same_index != (relation == GPUPhysicalBindingState.BOUND)
            ):
                raise GPUInventoryBusyError(
                    "GPU history retained observations have conflicting physical mappings."
                )
    if (
        binding.state != GPUPhysicalBindingState.BOUND
        or binding.device is None
        or matches[0].get("control_binding_state") in ("identity_conflict", "invalid_response")
        or sum(entry.get("device_id") == binding.device.device_id for entry in gpus) != 1
        or revision != gpu_info_cache_service.revision()
    ):
        raise GPUInventoryBusyError("GPU history lacks a unique current-revision physical mapping.")
    return GPUHistoryDeviceResolution(binding.device, observation.observed_at_ms, stale, revision)
