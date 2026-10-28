"""SoAI - Bounded Darwin profiler and IORegistry GPU discovery [backend/hardware/gpu_inventory/darwin_inventory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from math import ceil
from time import monotonic
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_physical_identity import GPUInventoryReadState
from core.logging.trace import get_logger
from hardware.gpu_inventory.darwin_registry import parse_darwin_registry
from hardware.gpu_inventory.entries import build_gpu_entry
from hardware.gpu_inventory.physical_observations import select_gpu_physical_read_state
from hardware.operations import create_device_id

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

LOGGER_NAME = "SoAI.hardware.gpu_inventory.darwin_inventory"


__all__ = (
    "DarwinGpuInventory",
    "read_darwin_gpu_inventory",
)

_OPERATION = "hardware.gpu_inventory.darwin_inventory"
_QUERY_FAILURES: tuple[type[Exception], ...] = (*RECOVERABLE_EXCEPTIONS, OSError)


@dataclass(frozen=True, slots=True)
class DarwinGpuInventory:
    gpus: list[JSONDict]
    state: GPUInventoryReadState
    reason_code: str | None
    diagnostics: tuple[SoAIError, ...]


def read_darwin_gpu_inventory(executor: CommandExecutorProtocol) -> DarwinGpuInventory:
    deadline = monotonic() + 30
    diagnostics: list[SoAIError] = []
    states: list[GPUInventoryReadState] = []
    profiler: list[JSONDict] = []
    registry: list[JSONDict] = []
    for command, source in (
        (["system_profiler", "SPDisplaysDataType"], "profiler"),
        (["ioreg", "-a", "-l", "-p", "IOService"], "registry"),
    ):
        try:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError("Darwin GPU acquisition deadline expired.")
            result = executor.execute(command, timeout=ceil(remaining), shell=False, use_sudo=False)
        except _QUERY_FAILURES as exception:
            state = GPUInventoryReadState.QUERY_FAILED
            if isinstance(exception, PermissionError):
                state = GPUInventoryReadState.PERMISSION_DENIED
            elif isinstance(exception, FileNotFoundError):
                state = GPUInventoryReadState.RUNTIME_UNAVAILABLE
            diagnostics.append(
                StateError(
                    "Darwin GPU physical query is unavailable.",
                    operation=_OPERATION,
                    cause=exception,
                )
            )
            states.append(state)
            continue
        if result is None or result.return_code != 0:
            diagnostics.append(
                StateError(
                    "Darwin GPU query is unavailable.",
                    operation=_OPERATION,
                    details=(
                        None
                        if result is None
                        else {
                            "return_code": result.return_code,
                            "stderr": result.stderr,
                            "stdout": result.stdout,
                        }
                    ),
                )
            )
            states.append(
                GPUInventoryReadState.INVALID_RESPONSE
                if result is None
                else GPUInventoryReadState.QUERY_FAILED
            )
            continue
        try:
            if len(result.stdout) > 8388608:
                raise ValidationError("Darwin GPU response exceeds bounded input size.")
            if source == "profiler":
                profiler = _parse_profiler(result.stdout)
            else:
                registry = parse_darwin_registry(result.stdout)
        except ValidationError as exception:
            diagnostics.append(
                StateError(
                    "Darwin GPU physical response is invalid.",
                    operation=_OPERATION,
                    cause=exception,
                )
            )
            states.append(GPUInventoryReadState.INVALID_RESPONSE)
    rows = _join_observations(profiler, registry)
    if any(row.get("native_device_path") is None for row in rows):
        states.append(GPUInventoryReadState.RUNTIME_UNAVAILABLE)
        diagnostics.append(
            StateError(
                "Darwin GPU profiler facts have no unique physical registry relation.",
                operation=_OPERATION,
            )
        )
    state = select_gpu_physical_read_state(states)
    for diagnostic in diagnostics:
        log_exception(
            get_logger(LOGGER_NAME),
            diagnostic,
            message="Darwin GPU physical acquisition is incomplete (non-critical).",
            operation=_OPERATION,
            level="trace",
        )
    return DarwinGpuInventory(
        rows,
        state,
        None if state == GPUInventoryReadState.OBSERVED else "darwin_physical_scope_unavailable",
        tuple(diagnostics),
    )


def _parse_profiler(raw: str) -> list[JSONDict]:
    if not raw.strip() or raw.splitlines()[0].strip() != "Graphics/Displays:":
        raise ValidationError("Darwin GPU profiler framing is invalid.", details={"stdout": raw})
    records: list[JSONDict] = []
    current: dict[str, str] = {}
    nested = False
    for line in (*raw.splitlines()[1:], "    END:"):
        if not line.strip():
            continue
        indentation = len(line) - len(line.lstrip())
        if indentation == 4 and line.endswith(":"):
            if current:
                records.append(_profiler_record(current))
            current = {} if line.strip() == "END:" else {"name": line.strip()[:-1]}
            nested = False
        elif indentation == 6 and current and ":" in line:
            key, value = line.strip().split(":", 1)
            if key == "Displays":
                nested = True
            elif not nested:
                if key in current:
                    raise ValidationError("Darwin GPU profiler field is duplicated.")
                current[key] = value.strip()
        elif not nested:
            raise ValidationError("Darwin GPU profiler row framing is invalid.")
    return records


def _profiler_record(fields: dict[str, str]) -> JSONDict:
    if fields.get("Type") != "GPU" or not fields.get("Chipset Model"):
        raise ValidationError("Darwin GPU profiler lacks an actual GPU model/type.")
    vendor = fields.get("Vendor", "")
    vendor_id = {"Intel": "8086", "AMD": "1002", "ATI": "1002", "NVIDIA": "10de"}.get(
        vendor.split(" ")[0]
    )
    device_id = fields.get("Device ID")
    if device_id is not None and re.fullmatch(r"0x[0-9a-fA-F]{4}", device_id) is None:
        raise ValidationError("Darwin GPU profiler device identifier is invalid.")
    memory: int | None = None
    memory_type: str | None = None
    for key, value in fields.items():
        if key.startswith("VRAM"):
            match = re.fullmatch(r"(\d+)\s+(MB|GB)", value)
            if match is None:
                raise ValidationError("Darwin GPU profiler memory quantity is invalid.")
            memory = int(match.group(1)) * (1024 if match.group(2) == "GB" else 1)
            memory_type = "shared" if "Dynamic" in key else "dedicated"
    return {
        "name": fields["Chipset Model"],
        "pci_vendor_id": vendor_id,
        "pci_device_id": device_id[2:].lower() if device_id is not None else None,
        "memory_total_mb": memory,
        "memory_type": memory_type,
        "native_bus": fields.get("Bus"),
    }


def _join_observations(profiler: list[JSONDict], registry: list[JSONDict]) -> list[JSONDict]:
    rows: list[JSONDict] = []
    matched: set[int] = set()
    for observed in registry:
        matches = [
            index
            for index, candidate in enumerate(profiler)
            if candidate.get("pci_vendor_id") == observed["pci_vendor_id"]
            and candidate.get("pci_device_id") == observed["pci_device_id"]
        ]
        peers = [
            candidate
            for candidate in registry
            if candidate["pci_vendor_id"] == observed["pci_vendor_id"]
            and candidate["pci_device_id"] == observed["pci_device_id"]
        ]
        detail = profiler[matches[0]] if len(matches) == len(peers) == 1 else {}
        if matches:
            matched.update(matches)
        row = _build_row(observed, detail, len(rows))
        rows.append(row)
    rows.extend(
        _build_row({}, detail, len(rows) + offset)
        for offset, detail in enumerate(profiler)
        if offset not in matched
    )
    return rows


def _build_row(observed: JSONDict, detail: JSONDict, index: int) -> JSONDict:
    vendor_id = observed.get("pci_vendor_id", detail.get("pci_vendor_id"))
    vendor = {"8086": "intel", "1002": "amd", "10de": "nvidia"}.get(str(vendor_id), "unknown")
    identity = observed.get("native_device_path")
    name = detail.get("name", observed.get("name"))
    row = build_gpu_entry(
        vendor=vendor,
        index=index,
        vendor_id=index,
        device_id=(
            create_device_id("gpu", f"darwin-native-{sha256(identity.encode('utf-8')).hexdigest()}")
            if isinstance(identity, str)
            else None
        ),
        name=name if isinstance(name, str) else "Darwin GPU",
        memory_used_mb=0,
        memory_total_mb=0,
        percent_used=0.0,
    )
    row.update(observed)
    row.update(detail)
    row.update(
        {
            "compute_capable": True,
            "telemetry_available": False,
            "telemetry_unavailable_reason": "darwin_runtime_metrics_unavailable",
            "memory_used_mb": None,
            "memory_total_mb": detail.get("memory_total_mb"),
            "percent_used": None,
        }
    )
    return row
