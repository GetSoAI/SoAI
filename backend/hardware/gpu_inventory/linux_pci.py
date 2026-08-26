"""SoAI - Linux PCI GPU inventory reader [backend/hardware/gpu_inventory/linux_pci.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from hardware.gpu_inventory.display_adapters import classify_display_adapter
from hardware.gpu_inventory.entries import build_gpu_entry
from hardware.gpu_inventory.identity import normalize_pci_bdf
from hardware.operations import create_device_id
from hardware.probe_failure_logging import execute_hardware_probe_command
from hardware.vendors.vendor_types import (
    AMD_VENDOR,
    INTEL_VENDOR,
    NVIDIA_VENDOR,
    UNKNOWN_VENDOR,
)

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("LinuxGpuInventory", "read_linux_pci_gpu_inventory")

LOGGER_NAME = "SoAI.hardware.gpu_inventory.linux_pci"
OPERATION = "hardware.gpu_inventory.linux_pci"
GPU_CLASS_IDS = ("0300", "0302", "0380")
PCI_ID_PATTERN_TEXT = "\\[([0-9a-fA-F]{4})\\]"
PCI_TRAILING_ID_PATTERN_TEXT = "\\s*\\[[0-9a-fA-F]{4}\\]\\s*$"


@dataclass(frozen=True, slots=True)
class LinuxPciGpuRecord:
    slot: str
    pci_bdf: str
    pci_class: str
    pci_class_id: str
    pci_vendor_id: str
    pci_device_id: str | None
    vendor: str
    vendor_name: str
    device_name: str
    kernel_driver: str | None
    kernel_modules: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LinuxGpuInventory:
    gpus: list[JSONDict]
    display_adapters: list[JSONDict]


def read_linux_pci_gpu_inventory(executor: CommandExecutorProtocol) -> LinuxGpuInventory:
    result = execute_hardware_probe_command(
        executor,
        ["lspci", "-D", "-vmm", "-nn", "-k"],
        logger=get_logger(LOGGER_NAME),
        message="Linux PCI GPU inventory query failed.",
        operation=OPERATION,
        timeout=10,
    )
    if result is None:
        return LinuxGpuInventory(gpus=[], display_adapters=[])
    if result.return_code != 0 or not result.stdout.strip():
        return LinuxGpuInventory(gpus=[], display_adapters=[])
    records = _parse_lspci_records(result.stdout)
    gpu_records = sorted(
        (record for record in records if record.pci_class_id in GPU_CLASS_IDS),
        key=lambda record: record.slot,
    )
    return _partition_gpu_records(gpu_records)


def _partition_gpu_records(gpu_records: list[LinuxPciGpuRecord]) -> LinuxGpuInventory:
    vendor_counts: dict[str, int] = {}
    gpus: list[JSONDict] = []
    display_adapters: list[JSONDict] = []
    for record in gpu_records:
        adapter_type = classify_display_adapter(
            record.vendor,
            record.pci_vendor_id,
            record.kernel_driver,
        )
        if adapter_type is not None:
            display_adapters.append(
                _build_pci_entry(
                    record,
                    index=len(display_adapters),
                    vendor_id=len(display_adapters),
                    compute_capable=False,
                    display_adapter_type=adapter_type,
                ),
            )
            continue
        vendor_id = vendor_counts.get(record.vendor, 0)
        vendor_counts[record.vendor] = vendor_id + 1
        gpus.append(
            _build_pci_entry(
                record,
                index=len(gpus),
                vendor_id=vendor_id,
                compute_capable=True,
                display_adapter_type=None,
            ),
        )
    return LinuxGpuInventory(gpus=gpus, display_adapters=display_adapters)


def _build_pci_entry(
    record: LinuxPciGpuRecord,
    *,
    index: int,
    vendor_id: int,
    compute_capable: bool,
    display_adapter_type: str | None,
) -> JSONDict:
    gpu_entry = build_gpu_entry(
        vendor=record.vendor,
        index=index,
        vendor_id=vendor_id,
        device_id=create_device_id("gpu", f"{record.vendor}-pci-{record.pci_bdf}"),
        name=_build_display_name(record),
        memory_used_mb=0,
        memory_total_mb=0,
        percent_used=0.0,
        processes=[],
    )
    gpu_entry.update(
        {
            "compute_capable": compute_capable,
            "display_adapter_type": display_adapter_type,
            "telemetry_available": False,
            "telemetry_unavailable_reason": _telemetry_unavailable_reason(record),
            "pci_bdf": record.pci_bdf,
            "pci_bdf_full": record.slot,
            "pci_class": record.pci_class,
            "pci_class_id": record.pci_class_id,
            "pci_vendor_id": record.pci_vendor_id,
            "pci_device_id": record.pci_device_id,
            "kernel_driver": record.kernel_driver,
            "kernel_modules": list(record.kernel_modules),
        },
    )
    return gpu_entry


def _parse_lspci_records(output: str) -> list[LinuxPciGpuRecord]:
    records: list[LinuxPciGpuRecord] = []
    current: dict[str, list[str]] = {}
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line:
            _append_record(records, current)
            current = {}
            continue
        key, value = _split_record_line(line)
        if key:
            if key not in current:
                current[key] = []
            current[key].append(value)
    _append_record(records, current)
    return records


def _append_record(records: list[LinuxPciGpuRecord], raw_record: dict[str, list[str]]) -> None:
    slot = _first_value(raw_record, "Slot")
    class_text = _first_value(raw_record, "Class")
    vendor_text = _first_value(raw_record, "Vendor")
    device_text = _first_value(raw_record, "Device")
    pci_class_id = _last_pci_id(class_text)
    pci_vendor_id = _last_pci_id(vendor_text)
    if not slot or not pci_class_id or not pci_vendor_id:
        return
    pci_bdf = normalize_pci_bdf(slot)
    if not pci_bdf:
        return
    records.append(
        LinuxPciGpuRecord(
            slot=slot,
            pci_bdf=pci_bdf,
            pci_class=_strip_pci_id(class_text),
            pci_class_id=pci_class_id,
            pci_vendor_id=pci_vendor_id,
            pci_device_id=_last_pci_id(device_text),
            vendor=_vendor_from_pci_id(pci_vendor_id),
            vendor_name=_strip_pci_id(vendor_text),
            device_name=_strip_pci_id(device_text),
            kernel_driver=_first_optional_value(raw_record, "Driver"),
            kernel_modules=tuple(raw_record.get("Module", ())),
        ),
    )


def _split_record_line(line: str) -> tuple[str, str]:
    if ":" not in line:
        return ("", "")
    key, value = line.split(":", 1)
    return (key.strip(), value.strip())


def _first_value(raw_record: dict[str, list[str]], key: str) -> str:
    values = raw_record.get(key)
    if not values:
        return ""
    return values[0].strip()


def _first_optional_value(raw_record: dict[str, list[str]], key: str) -> str | None:
    value = _first_value(raw_record, key)
    return value or None


def _last_pci_id(value: str) -> str | None:
    matches = [match.group(1) for match in re.finditer(PCI_ID_PATTERN_TEXT, value)]
    if not matches:
        return None
    return matches[-1].lower()


def _strip_pci_id(value: str) -> str:
    match = re.search(PCI_TRAILING_ID_PATTERN_TEXT, value)
    stripped = value[: match.start()].strip() if match is not None else value.strip()
    return stripped or value.strip()


def _vendor_from_pci_id(pci_vendor_id: str) -> str:
    if pci_vendor_id == "10de":
        return NVIDIA_VENDOR
    if pci_vendor_id in {"1002", "1022"}:
        return AMD_VENDOR
    if pci_vendor_id == "8086":
        return INTEL_VENDOR
    return UNKNOWN_VENDOR


def _telemetry_unavailable_reason(record: LinuxPciGpuRecord) -> str:
    if record.vendor == NVIDIA_VENDOR and (record.kernel_driver or "").lower() != "nvidia":
        return "driver_inactive"
    return "tool_missing"


def _build_display_name(record: LinuxPciGpuRecord) -> str:
    if record.vendor == UNKNOWN_VENDOR:
        return record.device_name or "GPU"
    if record.device_name:
        return record.device_name
    return f"{record.vendor_name} GPU".strip()
