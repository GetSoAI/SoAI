"""SoAI - SoAIBench stable failure reasons [backend/hardware/soaibench/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import (
    ProcessError,
    ServiceUnavailableError,
    SoAIError,
    SoAITimeoutError,
    StateError,
)
from core.hardware.soaibench_workloads import SOAIBENCH_WORKLOAD_NAMES
from core.system.native_runtime_probes import RuntimeStartupTimeoutError
from core.types.json import JSONDict
from core.validation.numbers import coerce_float_from_json

__all__ = (
    "SoAIBenchUnsupported",
    "SoAIBenchRunningWithoutOwner",
    "SoAIBenchCompanionFailure",
    "SoAIBenchCompanionFinalizationError",
    "SoAIBenchHeartbeatSuperseded",
    "unsupported_guidance",
    "child_request_failure",
    "execution_failure_projection",
)

OPENCL_RECOVERY_GUIDANCE = (
    "Verify that the selected GPU driver and OpenCL runtime are responsive, then retry SoAI Bench."
)


class SoAIBenchUnsupported(Exception):
    reason: str
    message: str
    diagnostic: str | None

    def __init__(self, reason: str, message: str, diagnostic: str | None = None) -> None:
        super().__init__(reason, message, diagnostic)
        self.reason = reason
        self.message = message
        self.diagnostic = diagnostic


class SoAIBenchRunningWithoutOwner(StateError):
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class SoAIBenchCompanionFailure:
    code: str
    exception: BaseException


class SoAIBenchCompanionFinalizationError(Exception):
    durable_run: JSONDict
    failures: tuple[SoAIBenchCompanionFailure, ...]

    def __init__(
        self,
        durable_run: JSONDict,
        failures: tuple[SoAIBenchCompanionFailure, ...],
    ) -> None:
        super().__init__(durable_run, failures)
        self.durable_run = durable_run
        self.failures = failures


class SoAIBenchHeartbeatSuperseded(Exception):
    durable_run: JSONDict

    def __init__(self, durable_run: JSONDict) -> None:
        super().__init__(durable_run)
        self.durable_run = durable_run


def child_request_failure(
    exception: BaseException, *, details: JSONDict, during_startup: bool
) -> SoAIError:
    if isinstance(exception, SoAITimeoutError | RuntimeStartupTimeoutError):
        exception.details = {**(exception.details or {}), **details}
        return exception
    ipc_deadline = (
        isinstance(exception, ServiceUnavailableError)
        and exception.operation == "core.ipc.multiplexed.request.timeout"
        and isinstance(exception.cause, TimeoutError)
    )
    startup_deadline = (
        during_startup
        and isinstance(exception, ServiceUnavailableError)
        and exception.operation == "core.ipc.multiplexed.wait_for_worker"
    )
    if isinstance(exception, TimeoutError) or ipc_deadline or startup_deadline:
        if during_startup:
            return RuntimeStartupTimeoutError(
                "SoAI Bench OpenCL child did not connect before its startup deadline.",
                operation="hardware.soaibench.opencl_child.startup",
                cause=exception,
                details=details,
            )
        return SoAITimeoutError(
            "SoAI Bench OpenCL operation exceeded its deadline.",
            operation="hardware.soaibench.opencl_child",
            cause=exception,
            details=details,
        )
    failure_details = {
        **((exception.details or {}) if isinstance(exception, SoAIError) else {}),
        **details,
    }
    if failure_details.get("failure_type") is None:
        if failure_details.get("return_code") is not None or (
            isinstance(exception, ProcessError)
            and exception.operation == "core.ipc.managed_worker.spawn.exited_before_connect"
        ):
            failure_details["failure_type"] = "child_exit"
        elif isinstance(exception, ConnectionError) or (
            isinstance(exception, ServiceUnavailableError)
            and exception.operation
            in (
                "core.ipc.multiplexed.connection_drop",
                "core.ipc.multiplexed.request.no_worker",
            )
        ):
            failure_details["failure_type"] = "disconnected"
    return ProcessError(
        "SoAI Bench OpenCL child communication failed.",
        operation="hardware.soaibench.opencl_child",
        cause=exception,
        details=failure_details,
    )


@dataclass(frozen=True, slots=True)
class SoAIBenchExecutionFailure:
    reason: str
    message: str
    summary: JSONDict


def execution_failure_projection(
    exception: ProcessError | SoAITimeoutError,
) -> SoAIBenchExecutionFailure:
    details = exception.details or {}
    if isinstance(exception, RuntimeStartupTimeoutError):
        stage, reason = "startup", "opencl_startup_deadline"
        deadline = details.get("startup_deadline_seconds")
    elif isinstance(exception, SoAITimeoutError):
        operation = details.get("operation")
        phase = details.get("phase")
        if operation == "phase" and phase in SOAIBENCH_WORKLOAD_NAMES:
            stage, reason = f"{phase} phase", "opencl_phase_deadline"
        elif operation == "preflight":
            stage, reason = "preflight", "opencl_preflight_deadline"
        else:
            stage, reason = "OpenCL operation", "opencl_runtime_deadline"
        deadline = details.get("deadline_seconds")
    else:
        return _communication_failure_projection(details)
    seconds = coerce_float_from_json(
        deadline, default=None, allow_bool=False, allow_nonfinite=False
    )
    deadline_label = (
        f"{seconds:g}-second deadline" if seconds is not None and seconds > 0 else "deadline"
    )
    guidance = OPENCL_RECOVERY_GUIDANCE
    return SoAIBenchExecutionFailure(
        reason,
        f"SoAI Bench {stage} exceeded its {deadline_label}. {guidance}",
        {
            "failed_operation": (
                "startup"
                if isinstance(exception, RuntimeStartupTimeoutError)
                else (
                    details.get("operation")
                    if details.get("operation") in ("phase", "preflight", "discover_runtime")
                    else None
                )
            ),
            "failed_phase": (
                details.get("phase") if details.get("phase") in SOAIBENCH_WORKLOAD_NAMES else None
            ),
            "deadline_seconds": seconds,
            "guidance": guidance,
        },
    )


def _communication_failure_projection(details: JSONDict) -> SoAIBenchExecutionFailure:
    match details.get("failure_type"):
        case "child_exit":
            reason = "opencl_child_exited"
            message = "SoAI Bench OpenCL child exited before completing its operation."
        case "invalid_response":
            reason = "opencl_child_invalid_response"
            message = "SoAI Bench OpenCL child returned an invalid result."
        case "disconnected":
            reason = "opencl_child_disconnected"
            message = "SoAI Bench lost its connection to the OpenCL child."
        case _:
            return SoAIBenchExecutionFailure(
                "opencl_runtime_error", "SoAI Bench OpenCL child communication failed.", {}
            )
    return SoAIBenchExecutionFailure(
        reason,
        f"{message} {OPENCL_RECOVERY_GUIDANCE}",
        {"guidance": OPENCL_RECOVERY_GUIDANCE},
    )


def unsupported_guidance(reason: str) -> str:
    if reason == "opencl_loader_missing":
        return (
            "Install or update the vendor GPU driver with OpenCL support. "
            "On Linux, install the OpenCL ICD loader and the vendor GPU OpenCL ICD."
        )
    if reason == "opencl_platform_unavailable":
        return "Install a vendor OpenCL ICD so the system OpenCL loader exposes a platform."
    if reason == "opencl_runtime_error":
        return "Verify the selected GPU driver and OpenCL runtime are responsive."
    if reason == "opencl_gpu_device_unavailable":
        return "Install a vendor OpenCL runtime that exposes a GPU device."
    if reason == "opencl_device_match_missing":
        return "Install or update the selected GPU vendor driver so OpenCL exposes the same GPU."
    if reason == "opencl_device_match_ambiguous":
        return "OpenCL exposed multiple matching GPUs; select a GPU with a unique UUID or PCI identity."
    if reason == "opencl_device_identity_conflict":
        return "Refresh GPU inventory and update the vendor driver before retrying SoAI Bench."
    if reason == "opencl_custom_identity_unproved":
        return "Update the GPU driver so OpenCL exposes consistent physical GPU identity and vendor information."
    if reason == "opencl_compiler_unavailable":
        return "Install a vendor OpenCL runtime with an online compiler before retrying SoAI Bench."
    if reason == "opencl_kernel_execution_unavailable":
        return "Install a vendor OpenCL runtime that supports source-compiled kernels."
    if reason == "opencl_memory_insufficient":
        return "SoAI Bench requires a 256 MiB OpenCL allocation and sufficient total device memory."
    if reason == "gpu_driver_inactive":
        return (
            "Install a compatible GPU driver and reboot so the selected GPU binds to that driver."
        )
    if reason == "hardware_manager_unavailable":
        return "Enable hardware monitoring before starting SoAI Bench."
    if reason == "gpu_inventory_unavailable":
        return "Refresh GPU inventory before starting SoAI Bench."
    return "SoAI Bench is unsupported on the selected GPU in the current runtime."
