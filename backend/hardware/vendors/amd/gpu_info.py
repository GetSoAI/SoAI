"""SoAI - AMD GPU inventory snapshot [backend/hardware/vendors/amd/gpu_info.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.logging.trace import get_logger
from core.validation.coercion import coerce_non_negative_int_from_numberish
from hardware.gpu_inventory.entries import apply_gpu_clock_metrics, build_gpu_entry
from hardware.gpu_inventory.memory_metrics import memory_percent_used
from hardware.operations import create_device_id
from hardware.vendors.amd.amd_smi_parsing import (
    extract_amd_smi_numeric,
    extract_amd_smi_processes,
    extract_amd_smi_text,
    extract_amd_smi_watts,
)
from hardware.vendors.amd.amd_smi_payload_selection import (
    collect_amd_smi_gpu_payloads,
    select_amd_smi_payload_for_card,
)
from hardware.vendors.amd.availability import is_amd_smi_available
from hardware.vendors.amd.commands import execute_amd_smi_json_command
from hardware.vendors.amd.power_capabilities import query_amd_native_power_capabilities

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("get_amd_gpu_info",)

LOGGER_NAME = "SoAI.hardware.vendors.amd_gpu_info"
OPERATION = "hardware_amd.get_amd_gpu_info"
AMD_OPTIONAL_QUERY_FAILURES: tuple[type[Exception], ...] = (
    StateError,
    *RECOVERABLE_EXCEPTIONS,
)


def _read_payloads(
    executor: CommandExecutorProtocol,
    detailed: bool,
    logger: TraceLogger,
) -> tuple[JSONValue | None, JSONValue | None, JSONValue | None]:
    static_payload = execute_amd_smi_json_command(
        executor,
        ["amd-smi", "static", "-g", "all", "-a", "-b", "-d", "-v", "-l", "--json"],
        timeout=10,
    )
    metric_payload: JSONValue | None = None
    process_payload: JSONValue | None = None
    try:
        metric_payload = execute_amd_smi_json_command(
            executor,
            ["amd-smi", "metric", "-g", "all", "-p", "-c", "-t", "-u", "-m", "-f", "--json"],
            timeout=10,
        )
    except AMD_OPTIONAL_QUERY_FAILURES as exception:
        log_handled_exception(
            logger,
            exception,
            message="amd-smi GPU metric query failed (non-critical).",
            operation=OPERATION,
            level="trace",
        )
    if detailed:
        try:
            process_payload = execute_amd_smi_json_command(
                executor,
                ["amd-smi", "process", "-g", "all", "--json"],
                timeout=5,
            )
        except AMD_OPTIONAL_QUERY_FAILURES as exception:
            log_handled_exception(
                logger,
                exception,
                message="amd-smi GPU process query failed (non-critical).",
                operation=OPERATION,
                level="trace",
            )
    return (static_payload, metric_payload, process_payload)


def _resolve_stable_gpu_uuid(static_entry: JSONDict) -> str | None:
    identity = extract_amd_smi_text(
        static_entry,
        (
            ("uuid",),
            ("asic", "serial"),
            ("product", "serial"),
        ),
    )
    if identity is None:
        return None
    return f"amd-{identity}"


def _resolve_device_identity(static_entry: JSONDict, device_index: int) -> str | None:
    stable_identity = _resolve_stable_gpu_uuid(static_entry)
    if stable_identity is not None:
        return stable_identity
    bdf = extract_amd_smi_text(static_entry, (("bdf",),))
    if bdf is None:
        return None
    return f"amd-{device_index}-{bdf}"


def _build_gpu_entry(
    static_entry: JSONDict,
    metric_entry: JSONValue | None,
    process_entry: JSONValue | None,
    *,
    card_index: int,
    device_index: int,
    detailed: bool,
) -> JSONDict | None:
    primary_device_id = _resolve_device_identity(static_entry, device_index)
    if primary_device_id is None:
        return None
    total_mem = coerce_non_negative_int_from_numberish(
        extract_amd_smi_numeric(static_entry, (("vram", "size"), ("size",))),
    )
    observed_used_memory = extract_amd_smi_numeric(
        metric_entry, (("vram", "used"), ("memory", "used"))
    )
    used_mem = coerce_non_negative_int_from_numberish(observed_used_memory)
    name = (
        extract_amd_smi_text(static_entry, (("market", "name"), ("product", "name"))) or "AMD GPU"
    )
    percent_used = memory_percent_used(used_mem, total_mem)
    processes = extract_amd_smi_processes(process_entry) if detailed else []
    gpu_entry = build_gpu_entry(
        vendor="amd",
        index=device_index,
        vendor_id=card_index,
        device_id=create_device_id("gpu", primary_device_id),
        name=name,
        memory_used_mb=used_mem,
        memory_total_mb=total_mem,
        percent_used=percent_used,
        temperature=extract_amd_smi_numeric(
            metric_entry,
            (
                ("temperature", "edge", "value"),
                ("temperature", "hotspot", "value"),
                ("temperature",),
                ("hotspot",),
            ),
        ),
        utilization=extract_amd_smi_numeric(
            metric_entry,
            (
                ("usage", "gfx", "activity", "value"),
                ("gfx", "activity", "value"),
                ("gpu", "use", "value"),
                ("gfx", "busy", "value"),
                ("gfx", "activity"),
                ("gpu", "use"),
                ("gfx", "busy"),
            ),
        ),
        power_draw_watts=extract_amd_smi_watts(
            metric_entry,
            (
                ("power", "socket", "power", "value"),
                ("socket", "power", "value"),
                ("power", "usage", "value"),
                ("socket", "power"),
                ("power", "usage"),
            ),
        ),
        power_limit_watts=extract_amd_smi_watts(
            [static_entry, metric_entry], (("current", "power", "cap"),)
        ),
        processes=processes,
    )
    if observed_used_memory is None:
        gpu_entry["memory_used_mb"] = None
        gpu_entry["percent_used"] = None
    if metric_entry is None:
        gpu_entry["telemetry_available"] = False
        gpu_entry["telemetry_unavailable_reason"] = "metric_query_failed"
    elif detailed and process_entry is None:
        gpu_entry["telemetry_available"] = True
        gpu_entry["telemetry_unavailable_reason"] = "process_query_failed"
    apply_gpu_clock_metrics(
        gpu_entry,
        extract_amd_smi_numeric(
            metric_entry,
            (
                ("clock", "gfx", "clk", "value"),
                ("gfx", "clock"),
                ("gfx", "clk", "value"),
                ("sclk",),
            ),
        ),
        extract_amd_smi_numeric(
            metric_entry,
            (
                ("clock", "mem", "clk", "value"),
                ("mem", "clock"),
                ("mem", "clk", "value"),
                ("mclk",),
            ),
        ),
    )
    bdf = extract_amd_smi_text(static_entry, (("bdf",),))
    if bdf is not None:
        gpu_entry["pci_bdf"] = bdf
    stable_gpu_uuid = _resolve_stable_gpu_uuid(static_entry)
    if stable_gpu_uuid is not None:
        gpu_entry["gpu_uuid"] = stable_gpu_uuid
    gpu_entry["gpu_uuid_observations"] = [
        value
        for key, value in static_entry.items()
        if key.casefold() == "uuid" and value is not None and value != "N/A"
    ]
    pci_observations: list[JSONValue] = []
    for key, value in static_entry.items():
        if key.casefold() == "bdf" and value is not None and value != "N/A":
            pci_observations.append(value)
        if key.casefold() == "bus" and isinstance(value, dict):
            pci_observations.extend(
                observation
                for field, observation in value.items()
                if field.casefold() == "bdf" and observation is not None and observation != "N/A"
            )
    gpu_entry["pci_bdf_observations"] = pci_observations
    for observation in pci_observations:
        if isinstance(observation, str) and normalize_observed_full_pci_bdf(observation):
            gpu_entry["pci_bdf_full"] = observation
            break
    return gpu_entry


def get_amd_gpu_info(
    executor: CommandExecutorProtocol,
    detailed: bool,
    index_offset: int,
) -> tuple[list[JSONDict], JSONDict]:
    logger = get_logger(LOGGER_NAME)
    if not is_amd_smi_available():
        return ([], {})
    try:
        static_payload, metric_payload, process_payload = _read_payloads(executor, detailed, logger)
        static_entries = collect_amd_smi_gpu_payloads(static_payload)
        if not static_entries and static_payload != []:
            raise StateError("AMD SMI returned no recognizable static GPU data.")
    except AMD_OPTIONAL_QUERY_FAILURES as exception:
        log_handled_exception(
            logger,
            exception,
            message="amd-smi GPU inventory query failed (non-critical).",
            operation=OPERATION,
            level="warning",
        )
        return ([], {})
    gpus: list[JSONDict] = []
    total_cards = len(static_entries)
    for card_index, static_entry in enumerate(static_entries):
        device_index = card_index + index_offset
        metric_entry = select_amd_smi_payload_for_card(
            metric_payload,
            static_entry,
            card_index,
            total_cards,
        )
        process_entry = select_amd_smi_payload_for_card(
            process_payload,
            static_entry,
            card_index,
            total_cards,
        )
        gpu_entry = _build_gpu_entry(
            static_entry,
            metric_entry,
            process_entry,
            card_index=card_index,
            device_index=device_index,
            detailed=detailed,
        )
        if gpu_entry is None:
            log_exception(
                logger,
                StateError(
                    f"AMD GPU unique identifier is required for device identity (index {device_index}).",
                ),
                message="Skipping AMD GPU entry without a unique identifier.",
                operation=OPERATION,
            )
            continue
        native_power = query_amd_native_power_capabilities(executor, logger, gpu_entry)
        if native_power is not None and "current" in native_power:
            gpu_entry["power_limit_watts"] = native_power["current"]
        gpus.append(gpu_entry)
    driver_version = _extract_driver_version(static_payload)
    drivers: JSONDict = {}
    if driver_version is not None:
        drivers["AMDGPU"] = {"version": driver_version, "driver_version": driver_version}
    return (gpus, drivers)


def _extract_driver_version(payload: JSONValue | None) -> str | None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if isinstance(key, str) and key.lower() == "driver" and isinstance(value, Mapping):
                version = value.get("VERSION") or value.get("version")
                return version if isinstance(version, str) and version else None
            nested = _extract_driver_version(value)
            if nested is not None:
                return nested
    if isinstance(payload, list):
        for value in payload:
            nested = _extract_driver_version(value)
            if nested is not None:
                return nested
    return None
