"""SoAI - Independent observed AMD power limits and native domain projection [backend/hardware/vendors/amd/power_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.logging.trace import get_logger
from hardware.gpu_capabilities.payloads import update_control_capability_section
from hardware.gpu_inventory.physical_binding import resolve_gpu_physical_binding
from hardware.vendors.amd.amd_smi_parsing import extract_amd_smi_watts
from hardware.vendors.amd.native_control_observations import acquire_amd_control_state

if TYPE_CHECKING:
    from core.logging.trace import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue


LOGGER_NAME = "SoAI.hardware.vendors.power_capabilities"
OPERATION_HARDWARE_AMD_NATIVE_POWER_CAPABILITIES = "hardware.amd.native_power_capabilities"


__all__ = (
    "AMD_POWER_QUERY_FAILURES",
    "apply_amd_smi_power_capabilities",
    "query_amd_native_power_capabilities",
)

AMD_POWER_QUERY_FAILURES: tuple[type[Exception], ...] = (
    StateError,
    ValidationError,
    OSError,
    *RECOVERABLE_EXCEPTIONS,
)


def apply_amd_smi_power_capabilities(gpu_caps: JSONDict, static_payload: JSONValue) -> None:
    min_power = extract_amd_smi_watts(static_payload, (("min", "power"),))
    max_power = extract_amd_smi_watts(static_payload, (("max", "power"), ("power", "cap", "max")))
    if min_power is None or max_power is None or min_power >= max_power:
        return
    default = extract_amd_smi_watts(static_payload, (("default", "power", "cap"),))
    current = extract_amd_smi_watts(static_payload, (("current", "power", "cap"),))
    update_control_capability_section(
        gpu_caps,
        "power_limit_watts",
        {
            "min": min_power,
            "max": max_power,
            "default": (
                default if default is not None and min_power <= default <= max_power else None
            ),
            "current": (
                current if current is not None and min_power <= current <= max_power else None
            ),
            "supported": True,
            "requires_admin": True,
            "control_backend": "amd_smi",
        },
    )


def query_amd_native_power_capabilities(
    executor: CommandExecutorProtocol, logger: TraceLogger | None, selected: JSONDict
) -> JSONDict | None:
    binding = resolve_gpu_physical_binding(selected, [selected])
    target = binding.device
    if binding.state != GPUPhysicalBindingState.BOUND or target is None:
        return None
    if target.vendor != "amd" or target.identity.pci_bdf_full is None:
        return None
    try:
        state = acquire_amd_control_state(executor, target=target, fields=("power_limit",))
        if not state.power_domains:
            return None
        minimum = max(power.minimum for power in state.power_domains)
        maximum = min(power.maximum for power in state.power_domains)
        if minimum >= maximum:
            raise StateError("AMD native power domains have no common configurable range.")
        currents = {power.current for power in state.power_domains}
        defaults = {power.default for power in state.power_domains}
        current = next(iter(currents)) if len(currents) == 1 else None
        default = next(iter(defaults)) if len(defaults) == 1 else None
        return {
            "min": minimum / 1000000,
            "max": maximum / 1000000,
            "current": current / 1000000 if current is not None else None,
            "default": default / 1000000 if default is not None else None,
            "supported": True,
            "requires_admin": True,
            "control_backend": "amd_smi",
            "unsupported_reason": None,
            "unit": "W",
            "error": None,
        }
    except AMD_POWER_QUERY_FAILURES as exception:
        log_handled_exception(
            logger or get_logger(LOGGER_NAME),
            exception,
            message="AMD native power capability query is unavailable.",
            operation=OPERATION_HARDWARE_AMD_NATIVE_POWER_CAPABILITIES,
            details={"device_id": target.device_id},
            level="trace",
        )
        return {
            "error": ErrorPublicPayload(
                code="process_error",
                message="AMD power observations are unavailable.",
                details={"reason": "native_power_query_failed"},
            ).to_dict(),
        }
