"""SoAI - NVIDIA NVML scan device identity reads [backend/hardware/vendors/nvidia/scan_device_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

import pynvml

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from hardware.gpu_inventory.identity import normalize_pci_bdf
from hardware.operations import create_device_id
from hardware.vendors.nvidia.discovery import normalize_gpu_name
from hardware.vendors.nvidia.internal_protocols import (
    NvmlDeviceGetNameProtocol,
    NvmlDeviceGetPciInfoProtocol,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger

__all__ = (
    "read_gpu_name",
    "read_pci_identity",
    "read_primary_device_id",
)

OPERATION = "hardware.nvidia.scan.read_uuid"


def read_gpu_name(handle: ctypes.c_void_p) -> str:
    try:
        device_get_name = pynvml.nvmlDeviceGetName
    except AttributeError:
        device_get_name = None
    gpu_name = "NVIDIA GPU"
    if isinstance(device_get_name, NvmlDeviceGetNameProtocol):
        name_value = device_get_name(handle)
        if isinstance(name_value, str | bytes):
            gpu_name = normalize_gpu_name(name_value)
    return gpu_name


def read_pci_identity(
    handle: ctypes.c_void_p,
    *,
    logger: TraceLogger,
    device_index: int,
) -> tuple[str | None, str | None, list[str]]:
    try:
        device_get_pci_info = pynvml.nvmlDeviceGetPciInfo
    except AttributeError:
        device_get_pci_info = None
    if not isinstance(device_get_pci_info, NvmlDeviceGetPciInfoProtocol):
        return (None, None, [])
    try:
        pci_info = device_get_pci_info(handle)
        bus_id = pci_info.busId
        bus_id_text = (
            bus_id.decode("utf-8", errors="replace") if isinstance(bus_id, bytes) else bus_id
        )
        pci_bdf = normalize_pci_bdf(bus_id_text)
        pci_bdf_full = bus_id_text if normalize_observed_full_pci_bdf(bus_id_text) else None
        return (pci_bdf or None, pci_bdf_full, [bus_id_text] if bus_id_text else [])
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read NVIDIA GPU PCI identity (non-critical).",
            operation=OPERATION,
            details={"device_index": device_index},
            level="trace",
        )
        return (None, None, [])


def read_primary_device_id(
    handle: ctypes.c_void_p,
    *,
    logger: TraceLogger,
    device_index: int,
) -> str:
    primary_device_id: str | None = None
    try:
        device_get_uuid = pynvml.nvmlDeviceGetUUID
    except AttributeError:
        device_get_uuid = None
    if callable(device_get_uuid):
        try:
            raw_uuid = device_get_uuid(handle)
            if raw_uuid:
                primary_device_id = f"nvidia-{raw_uuid}"
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to read NVIDIA GPU UUID (non-critical).",
                operation=OPERATION,
                details={"device_index": device_index},
                level="trace",
            )
    if not primary_device_id:
        raise StateError(f"NVIDIA GPU UUID is required for device identity (index {device_index}).")
    return create_device_id("gpu", primary_device_id)
