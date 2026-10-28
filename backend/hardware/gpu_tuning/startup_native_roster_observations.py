"""SoAI - Native GPU roster identity projection and acquisition failure classification [backend/hardware/gpu_tuning/startup_native_roster_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.hardware.gpu_physical_identity import (
    GPUInventoryReadState,
    GPUPhysicalDevice,
    GPUPhysicalIdentity,
)
from hardware.gpu_tuning.startup_scope_types import GPULegacyResetRoster
from hardware.operations import create_device_id

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict

OPERATION_HARDWARE_GPU_TUNING_STARTUP_SCOPE_ACQUISITION_NATIVE_ROSTER = (
    "hardware.gpu_tuning.startup_scope_acquisition.native_roster"
)

__all__ = (
    "absent_native_roster",
    "failed_native_roster",
    "native_roster_device",
    "unavailable_nvidia_roster",
)


def unavailable_nvidia_roster(
    backend: str, acquisition_id: str, reason: str
) -> GPULegacyResetRoster:
    return GPULegacyResetRoster(
        "nvidia", backend, acquisition_id, GPUInventoryReadState.RUNTIME_UNAVAILABLE, (), reason
    )


def failed_native_roster(
    vendor: str, backend: str, acquisition_id: str, logger: TraceLogger, exception: Exception
) -> GPULegacyResetRoster:
    details: JSONDict = {"vendor": vendor, "backend": backend, "acquisition_id": acquisition_id}
    if isinstance(exception, SoAIError) and exception.details is not None:
        details["native_details"] = dict(exception.details)
    log_exception(
        logger,
        exception,
        message="GPU startup native roster acquisition failed.",
        operation=OPERATION_HARDWARE_GPU_TUNING_STARTUP_SCOPE_ACQUISITION_NATIVE_ROSTER,
        details=details,
        level="warning",
    )
    return GPULegacyResetRoster(
        vendor,
        backend,
        acquisition_id,
        (
            GPUInventoryReadState.INVALID_RESPONSE
            if isinstance(exception, ValidationError)
            else GPUInventoryReadState.QUERY_FAILED
        ),
        (),
        "native_roster_query_failed",
    )


def native_roster_device(
    vendor: str, identity: GPUPhysicalIdentity, observations: tuple[str, ...]
) -> GPUPhysicalDevice:
    return GPUPhysicalDevice(
        create_device_id("gpu", identity.uuid or f"{vendor}-pci-{identity.pci_bdf_full}"),
        vendor,
        identity,
        None,
        None,
        observations,
    )


def absent_native_roster(vendor: str, backend: str, acquisition_id: str) -> GPULegacyResetRoster:
    return GPULegacyResetRoster(
        vendor,
        backend,
        acquisition_id,
        GPUInventoryReadState.OBSERVED,
        (),
        "physical_vendor_absent",
    )
