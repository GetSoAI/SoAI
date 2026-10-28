"""SoAI - Strict fresh Linux PCI physical acquisition [backend/hardware/gpu_inventory/linux_physical_acquisition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, SoAITimeoutError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_physical_identity import GPUInventoryReadState
from core.logging.trace import get_logger
from hardware.gpu_inventory.identity import normalize_pci_bdf
from hardware.gpu_inventory.linux_pci_sysfs import iter_linux_pci_sysfs_records
from hardware.vendors.vendor_types import AMD_VENDOR, INTEL_VENDOR, NVIDIA_VENDOR, UNKNOWN_VENDOR

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol

__all__ = (
    "LOGGER_NAME",
    "OPERATION",
    "PCI_QUERY_FAILURES",
    "GPU_CLASS_IDS",
    "PCI_ID_PATTERN_TEXT",
    "PCI_TRAILING_ID_PATTERN_TEXT",
    "LinuxPciGpuRecord",
    "LinuxPhysicalAcquisition",
    "read_linux_physical_acquisition",
)

LOGGER_NAME = "SoAI.hardware.gpu_inventory.linux_physical_acquisition"
OPERATION = "hardware.gpu_inventory.linux_physical_acquisition"
PCI_QUERY_FAILURES: tuple[type[Exception], ...] = (*RECOVERABLE_EXCEPTIONS, OSError)
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
    raw_fields: dict[str, list[str]]


@dataclass(frozen=True, slots=True)
class LinuxPhysicalAcquisition:
    records: tuple[LinuxPciGpuRecord, ...]
    state: GPUInventoryReadState
    reason_code: str | None
    raw_output: str | None
    diagnostics: tuple[SoAIError, ...]


def read_linux_physical_acquisition(
    executor: CommandExecutorProtocol, *, sysfs_root: str = "/sys"
) -> LinuxPhysicalAcquisition:
    try:
        result = executor.execute(
            ["lspci", "-D", "-vmm", "-nn", "-k"], timeout=10, shell=False, use_sudo=False
        )
    except PCI_QUERY_FAILURES as exception:
        if isinstance(exception, FileNotFoundError):
            return _read_sysfs_acquisition(sysfs_root)
        state = GPUInventoryReadState.QUERY_FAILED
        if isinstance(exception, PermissionError):
            state = GPUInventoryReadState.PERMISSION_DENIED
        error = StateError(
            "Linux PCI inventory query failed.", operation=OPERATION, cause=exception
        )
        log_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Linux PCI inventory query failed (non-critical).",
            operation=OPERATION,
            level="trace",
        )
        return LinuxPhysicalAcquisition((), state, "pci_query_unavailable", None, (error,))
    if result is None:
        error = StateError("GPU inventory executor returned no response.", operation=OPERATION)
        log_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Linux PCI response is missing (non-critical).",
            operation=OPERATION,
            level="trace",
        )
        return LinuxPhysicalAcquisition(
            (), GPUInventoryReadState.INVALID_RESPONSE, "pci_response_missing", None, (error,)
        )
    if result.return_code != 0:
        if result.return_code == 127 and result.startup_failure == "not_found":
            return _read_sysfs_acquisition(sysfs_root)
        error = StateError(
            "Linux PCI inventory response is unavailable.",
            operation=OPERATION,
            details={
                "return_code": result.return_code,
                "stderr": result.stderr,
                "stdout": result.stdout,
            },
        )
        log_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Linux PCI response is unavailable (non-critical).",
            operation=OPERATION,
            level="trace",
        )
        return LinuxPhysicalAcquisition(
            (), GPUInventoryReadState.QUERY_FAILED, "pci_query_failed", result.stdout, (error,)
        )
    records, invalid_diagnostics = _parse_lspci_records(result.stdout)
    return _complete_acquisition(records, invalid_diagnostics, result.stdout)


def _complete_acquisition(
    records: list[LinuxPciGpuRecord],
    invalid_diagnostics: tuple[SoAIError, ...],
    raw_output: str | None,
) -> LinuxPhysicalAcquisition:
    uncovered = tuple(
        StateError(
            "Linux PCI display class coverage is unavailable.",
            operation=OPERATION,
            details={"raw_record": record.raw_fields},
        )
        for record in records
        if record.pci_class_id.startswith("03") and record.pci_class_id not in GPU_CLASS_IDS
    )
    diagnostics = invalid_diagnostics + uncovered
    for diagnostic in diagnostics:
        log_exception(
            get_logger(LOGGER_NAME),
            diagnostic,
            message="Linux PCI row cannot establish complete physical coverage (non-critical).",
            operation=OPERATION,
            level="trace",
        )
    state = GPUInventoryReadState.OBSERVED
    reason = None
    if invalid_diagnostics:
        state, reason = GPUInventoryReadState.INVALID_RESPONSE, "pci_response_invalid"
    elif uncovered:
        state, reason = GPUInventoryReadState.RUNTIME_UNAVAILABLE, "pci_display_class_uncovered"
    return LinuxPhysicalAcquisition(tuple(records), state, reason, raw_output, diagnostics)


def _read_sysfs_acquisition(sysfs_root: str) -> LinuxPhysicalAcquisition:
    records: list[LinuxPciGpuRecord] = []
    try:
        for fields in iter_linux_pci_sysfs_records(sysfs_root):
            _append_record(records, fields)
    except (OSError, SoAITimeoutError, ValidationError) as exception:
        state = GPUInventoryReadState.QUERY_FAILED
        reason = "pci_sysfs_query_failed"
        if isinstance(exception, PermissionError):
            state = GPUInventoryReadState.PERMISSION_DENIED
        elif isinstance(exception, FileNotFoundError):
            state = GPUInventoryReadState.RUNTIME_UNAVAILABLE
        elif isinstance(exception, ValidationError):
            state = GPUInventoryReadState.INVALID_RESPONSE
        elif isinstance(exception, SoAITimeoutError):
            reason = "pci_sysfs_acquisition_deadline_expired"
        error = StateError(
            "Linux kernel PCI inventory is unavailable.", operation=OPERATION, cause=exception
        )
        return LinuxPhysicalAcquisition(tuple(records), state, reason, None, (error,))
    return _complete_acquisition(records, (), None)


def _parse_lspci_records(output: str) -> tuple[list[LinuxPciGpuRecord], tuple[SoAIError, ...]]:
    records: list[LinuxPciGpuRecord] = []
    diagnostics: list[SoAIError] = []
    current: dict[str, list[str]] = {}
    for raw_line in (*output.splitlines(), ""):
        line = raw_line.rstrip()
        if not line:
            if current:
                try:
                    _append_record(records, current)
                except ValidationError as exception:
                    diagnostics.append(exception)
                current = {}
            continue
        key, value = _split_record_line(line)
        if not key:
            diagnostics.append(
                ValidationError(
                    "Linux PCI row framing is invalid.",
                    operation=OPERATION,
                    details={"raw_line": raw_line},
                )
            )
            continue
        if key not in current:
            current[key] = []
        current[key].append(value)
    return records, tuple(diagnostics)


def _append_record(records: list[LinuxPciGpuRecord], raw_record: dict[str, list[str]]) -> None:
    slot = _first_value(raw_record, "Slot")
    class_text = _first_value(raw_record, "Class")
    vendor_text = _first_value(raw_record, "Vendor")
    device_text = _first_value(raw_record, "Device")
    pci_class_id = _last_pci_id(class_text)
    pci_vendor_id = _last_pci_id(vendor_text)
    full_slot = normalize_observed_full_pci_bdf(slot)
    if (
        not full_slot
        or not pci_class_id
        or not pci_vendor_id
        or any(len(raw_record.get(field, ())) != 1 for field in ("Slot", "Class", "Vendor"))
        or any(normalize_observed_full_pci_bdf(record.slot) == full_slot for record in records)
    ):
        raise ValidationError(
            "Linux PCI row identity is invalid or duplicated.",
            operation=OPERATION,
            details={"raw_record": {key: list(values) for key, values in raw_record.items()}},
        )
    pci_bdf = normalize_pci_bdf(slot)
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
            raw_fields={key: list(values) for key, values in raw_record.items()},
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
