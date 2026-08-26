"""SoAI - SoAIBench GPU identity extraction [backend/hardware/soaibench/gpu_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json_value import coerce_json_dict_or_empty
from hardware.control_snapshots import find_gpu_entry
from hardware.gpu_inventory.identity import (
    normalize_identity_index,
    normalize_model_key,
    optional_identity_text,
    snapshot_gpu_entries,
    uuid_from_device_id,
)
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.vendors.vendor_metadata import resolve_driver_version_by_vendor_prefix

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "identity_from_payload",
    "identity_payload",
    "identity_payload_for_history",
    "resolve_gpu_identity",
)


def resolve_gpu_identity(snapshot: JSONDict, device_id: str) -> SoAIBenchGpuIdentity:
    gpu = find_gpu_entry(snapshot, device_id)
    if gpu is None:
        raise ValidationError(f"GPU inventory is unavailable for {device_id}.")
    name = optional_identity_text(gpu.get("name"))
    vendor = optional_identity_text(gpu.get("type")) or optional_identity_text(gpu.get("vendor"))
    model_key = optional_identity_text(gpu.get("gpu_model_key")) or normalize_model_key(name)
    driver_version = (
        optional_identity_text(gpu.get("driver_version"))
        or optional_identity_text(gpu.get("driver"))
        or _driver_version(snapshot, vendor)
    )
    device_id_value = optional_identity_text(gpu.get("device_id"))
    return SoAIBenchGpuIdentity(
        device_id=device_id,
        gpu_name=name,
        gpu_model_key=model_key,
        vendor=vendor,
        driver_version=driver_version,
        gpu_uuid=(
            optional_identity_text(gpu.get("uuid"))
            or optional_identity_text(gpu.get("gpu_uuid"))
            or uuid_from_device_id(device_id_value)
        ),
        pci_bdf=optional_identity_text(gpu.get("pci_bdf"))
        or optional_identity_text(gpu.get("pci_bus_id")),
        kernel_driver=optional_identity_text(gpu.get("kernel_driver")),
        operating_system=optional_identity_text(gpu.get("os")),
        gpu_index=normalize_identity_index(gpu.get("index")),
    )


def identity_payload(identity: SoAIBenchGpuIdentity) -> JSONDict:
    return {
        "device_id": identity.device_id,
        "gpu_name": identity.gpu_name,
        "gpu_model_key": identity.gpu_model_key,
        "vendor": identity.vendor,
        "driver_version": identity.driver_version,
        "gpu_uuid": identity.gpu_uuid,
        "pci_bdf": identity.pci_bdf,
        "kernel_driver": identity.kernel_driver,
        "os": identity.operating_system,
        "gpu_index": identity.gpu_index,
    }


def identity_payload_for_history(snapshot: JSONDict, identity: SoAIBenchGpuIdentity) -> JSONDict:
    payload = identity_payload(identity)
    if not _model_key_is_unique_in_snapshot(snapshot, identity.gpu_model_key):
        payload["gpu_model_key"] = None
    return payload


def identity_from_payload(payload: JSONDict) -> SoAIBenchGpuIdentity:
    return SoAIBenchGpuIdentity(
        device_id=str(payload["device_id"]),
        gpu_name=optional_identity_text(payload.get("gpu_name")),
        gpu_model_key=optional_identity_text(payload.get("gpu_model_key")),
        vendor=optional_identity_text(payload.get("vendor")),
        driver_version=optional_identity_text(payload.get("driver_version")),
        gpu_uuid=optional_identity_text(payload.get("gpu_uuid")),
        pci_bdf=optional_identity_text(payload.get("pci_bdf")),
        kernel_driver=optional_identity_text(payload.get("kernel_driver")),
        operating_system=optional_identity_text(payload.get("os")),
        gpu_index=normalize_identity_index(payload.get("gpu_index")),
    )


def _driver_version(snapshot: JSONDict, vendor: str | None) -> str | None:
    gpu_payload = coerce_json_dict_or_empty(snapshot.get("gpu"))
    drivers = gpu_payload.get("compute_drivers")
    if not isinstance(drivers, dict):
        return None
    return resolve_driver_version_by_vendor_prefix(drivers, vendor)


def _model_key_is_unique_in_snapshot(snapshot: JSONDict, model_key: str | None) -> bool:
    if model_key is None:
        return False
    matches = 0
    for gpu in snapshot_gpu_entries(snapshot):
        name = optional_identity_text(gpu.get("name"))
        candidate = optional_identity_text(gpu.get("gpu_model_key")) or normalize_model_key(name)
        if candidate == model_key:
            matches += 1
    return matches == 1
