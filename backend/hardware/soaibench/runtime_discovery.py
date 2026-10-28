"""SoAI - Strong physical OpenCL discovery through the existing supervised child pool [backend/hardware/soaibench/runtime_discovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import math
import os
from dataclasses import replace
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ProcessError, SoAITimeoutError, ValidationError
from core.hardware.gpu_identity_normalization import (
    normalize_identity_name,
    normalize_observed_full_pci_bdf,
)
from core.hardware.gpu_physical_identity import (
    GPUInventoryReadState,
    GPUPhysicalDevice,
    GPUPhysicalSnapshot,
)
from core.hardware.opencl_runtime_types import (
    OpenCLRuntimeSnapshot,
    OpenCLRuntimeState,
    OpenCLRuntimeTarget,
)
from core.runtime.platform import get_runtime_platform
from core.system.native_runtime_probes import RuntimeStartupTimeoutError
from core.timing.epoch import epoch_ms
from hardware.gpu_inventory.physical_snapshot import acquire_gpu_physical_snapshot
from hardware.soaibench.device_matching import (
    STRONG_MATCH_BASES,
    match_opencl_device,
    opencl_vendor_matches,
)
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.gpu_identity import opencl_target_identity
from hardware.soaibench.opencl_devices import enumerate_opencl_gpu_devices
from hardware.soaibench.opencl_runtime import build_opencl_runtime, release_opencl_runtime

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.system.protocols import CommandExecutorProtocol
    from hardware.soaibench.internal_protocols import SoAIBenchOpenCLPoolProtocol

OPERATION_HARDWARE_SOAIBENCH_RUNTIME_DISCOVERY = "hardware.soaibench.runtime_discovery"


__all__ = (
    "acquire_opencl_runtime_snapshot",
    "discover_opencl_target",
    "probe_opencl_runtime",
    "unavailable_opencl_target",
)


def _discovery_message(state: OpenCLRuntimeState) -> str:
    match state:
        case OpenCLRuntimeState.PERMISSION_DENIED:
            return "OpenCL access is unavailable for the current service account."
        case OpenCLRuntimeState.ZERO_DEVICES:
            return "OpenCL did not expose any GPU devices for the selected vendor."
        case OpenCLRuntimeState.UNSUPPORTED:
            return "The selected GPU does not have a supported OpenCL runtime."
        case OpenCLRuntimeState.IDENTITY_CONFLICT:
            return "OpenCL physical identity conflicts with the selected GPU."
        case OpenCLRuntimeState.UNAVAILABLE:
            return "OpenCL runtime discovery is unavailable."
        case OpenCLRuntimeState.TIMED_OUT:
            return "SoAI Bench OpenCL child exceeded its deadline."
        case _:
            raise KeyError(state)


def unavailable_opencl_target(
    target: GPUPhysicalDevice, state: OpenCLRuntimeState, reason: str
) -> OpenCLRuntimeTarget:
    return OpenCLRuntimeTarget(
        target.device_id,
        target.vendor,
        state,
        reason,
        _discovery_message(state),
        None,
        None,
        None,
        None,
        None,
    )


def discover_opencl_target(target: GPUPhysicalDevice) -> OpenCLRuntimeTarget:
    uid = None if get_runtime_platform().is_windows else os.geteuid()
    gid = None if get_runtime_platform().is_windows else os.getegid()
    target_vendor_absence_proved = False
    try:
        identity = opencl_target_identity(target)
        candidates = enumerate_opencl_gpu_devices(identity)
        if not candidates:
            raise SoAIBenchUnsupported(
                reason="opencl_gpu_device_unavailable",
                message=_discovery_message(OpenCLRuntimeState.ZERO_DEVICES),
            )
        enumeration_warnings = next(
            (
                candidate.enumeration_warnings
                for candidate in candidates
                if candidate.enumeration_warnings
            ),
            (),
        )
        if enumeration_warnings:
            raise SoAIBenchUnsupported(
                reason="opencl_enumeration_incomplete",
                message=_discovery_message(OpenCLRuntimeState.UNAVAILABLE),
                diagnostic="; ".join(enumeration_warnings)[:8192],
            )
        target_vendor_absence_proved = normalize_identity_name(target.vendor) not in (
            "",
            "unknown",
        ) and all(
            normalize_identity_name(candidate.device_vendor) not in ("", "unknown")
            and not opencl_vendor_matches(
                target.vendor, candidate.device_vendor, candidate.platform_vendor
            )
            for candidate in candidates
        )
        matched = match_opencl_device(identity, candidates)
        if matched.match_basis not in STRONG_MATCH_BASES:
            raise SoAIBenchUnsupported(
                reason="opencl_device_identity_unproved",
                message=_discovery_message(OpenCLRuntimeState.IDENTITY_CONFLICT),
            )
        if matched.match_basis.startswith("pci_bdf"):
            selected_pci = normalize_observed_full_pci_bdf(target.identity.pci_bdf_full or "")
            observed_pci = normalize_observed_full_pci_bdf(matched.device.pci_bdf or "")
            if not selected_pci or selected_pci != observed_pci:
                raise SoAIBenchUnsupported(
                    reason="opencl_device_identity_unproved",
                    message=_discovery_message(OpenCLRuntimeState.IDENTITY_CONFLICT),
                )
        runtime = build_opencl_runtime(identity)
        try:
            if (
                runtime.device != matched.device.device_handle
                or runtime.match_basis not in STRONG_MATCH_BASES
                or runtime.enumeration_warnings
            ):
                raise SoAIBenchUnsupported(
                    reason="opencl_device_identity_changed",
                    message=_discovery_message(OpenCLRuntimeState.IDENTITY_CONFLICT),
                )
            observed = OpenCLRuntimeTarget(
                target.device_id,
                target.vendor,
                OpenCLRuntimeState.READY,
                None,
                "",
                matched.match_basis,
                runtime.platform_name,
                runtime.driver_version,
                uid,
                gid,
            )
        finally:
            release_opencl_runtime(runtime)
        return observed
    except PermissionError:
        state, reason = OpenCLRuntimeState.PERMISSION_DENIED, "opencl_permission_denied"
    except SoAIBenchUnsupported as exception:
        if exception.diagnostic:
            raise
        reason = exception.reason
        if reason == "opencl_gpu_device_unavailable" and exception.diagnostic is None:
            state = OpenCLRuntimeState.ZERO_DEVICES
        elif reason == "opencl_device_match_missing" and target_vendor_absence_proved:
            state = OpenCLRuntimeState.ZERO_DEVICES
        elif (
            reason.startswith("opencl_device_identity")
            or reason.startswith("opencl_device_match")
            or reason == "opencl_custom_identity_unproved"
        ):
            state = OpenCLRuntimeState.IDENTITY_CONFLICT
        elif reason in (
            "opencl_loader_missing",
            "opencl_library_unavailable",
            "opencl_platform_unavailable",
            "opencl_compiler_unavailable",
            "opencl_kernel_execution_unavailable",
        ):
            state = OpenCLRuntimeState.UNSUPPORTED
        else:
            state = OpenCLRuntimeState.UNAVAILABLE
    except (OSError, RuntimeError) as exception:
        state, reason = OpenCLRuntimeState.UNAVAILABLE, "opencl_runtime_error"
        diagnostic = str(exception)
        if diagnostic:
            raise SoAIBenchUnsupported(
                reason=reason, message=_discovery_message(state), diagnostic=diagnostic[:8192]
            ) from exception
    return replace(
        unavailable_opencl_target(target, state, reason), effective_uid=uid, effective_gid=gid
    )


async def probe_opencl_runtime(
    pool: SoAIBenchOpenCLPoolProtocol,
    snapshot: GPUPhysicalSnapshot,
    *,
    timeout_sec: float,
    logger: LoggerProtocol,
) -> OpenCLRuntimeSnapshot:
    if not math.isfinite(timeout_sec) or timeout_sec <= 0.0:
        raise ValidationError("OpenCL discovery timeout must be positive.")
    if len(snapshot.devices) > 256 or len({target.device_id for target in snapshot.devices}) != len(
        snapshot.devices
    ):
        raise ValidationError("OpenCL discovery requires a bounded unique physical scope.")
    if len(snapshot.vendors) > 256 or len({row.vendor for row in snapshot.vendors}) != len(
        snapshot.vendors
    ):
        raise ValidationError("OpenCL discovery requires unambiguous physical vendor observations.")
    observations: list[OpenCLRuntimeTarget] = []
    states = {row.vendor: row.state for row in snapshot.vendors}
    try:
        async with asyncio.timeout(timeout_sec):
            for target in snapshot.devices:
                if states.get(target.vendor) != GPUInventoryReadState.OBSERVED or (
                    target.identity.uuid is None and target.identity.pci_bdf_full is None
                ):
                    physical_state = states.get(target.vendor)
                    state = (
                        OpenCLRuntimeState.PERMISSION_DENIED
                        if physical_state == GPUInventoryReadState.PERMISSION_DENIED
                        else (
                            OpenCLRuntimeState.IDENTITY_CONFLICT
                            if physical_state
                            in (
                                GPUInventoryReadState.OBSERVED,
                                GPUInventoryReadState.INVALID_RESPONSE,
                            )
                            else OpenCLRuntimeState.UNAVAILABLE
                        )
                    )
                    observations.append(
                        unavailable_opencl_target(target, state, "physical_scope_unproved")
                    )
                    continue
                try:
                    async with pool.lease() as child:
                        observation = await child.discover_runtime(target, timeout_sec=timeout_sec)
                    expected_account = (
                        (None, None)
                        if get_runtime_platform().is_windows
                        else (os.geteuid(), os.getegid())
                    )
                    if observation.state == OpenCLRuntimeState.READY and (
                        observation.device_id != target.device_id
                        or observation.vendor != target.vendor
                        or (observation.effective_uid, observation.effective_gid)
                        != expected_account
                    ):
                        raise ProcessError(
                            "OpenCL readiness does not match its physical target and service account.",
                            operation="hardware.soaibench.runtime_discovery",
                        )
                    observations.append(observation)
                except RuntimeStartupTimeoutError:
                    raise
                except (ProcessError, SoAIBenchUnsupported) as exception:
                    if isinstance(exception, ProcessError):
                        log_handled_exception(
                            logger,
                            exception,
                            message="OpenCL runtime discovery failed for the selected GPU.",
                            operation=OPERATION_HARDWARE_SOAIBENCH_RUNTIME_DISCOVERY,
                            details={"device_id": target.device_id},
                            level="trace",
                        )
                    observations.append(
                        unavailable_opencl_target(
                            target, OpenCLRuntimeState.UNAVAILABLE, "opencl_runtime_error"
                        )
                    )
    except (TimeoutError, SoAITimeoutError, RuntimeStartupTimeoutError):
        remaining = snapshot.devices[len(observations) :]
        observations.extend(
            unavailable_opencl_target(
                target, OpenCLRuntimeState.TIMED_OUT, "opencl_discovery_deadline"
            )
            for target in remaining
        )
    return OpenCLRuntimeSnapshot(snapshot.acquisition_id, tuple(observations), snapshot.vendors)


async def acquire_opencl_runtime_snapshot(
    pool: SoAIBenchOpenCLPoolProtocol,
    command_executor: CommandExecutorProtocol,
    *,
    timeout_sec: float,
    logger: LoggerProtocol,
) -> OpenCLRuntimeSnapshot:
    if not math.isfinite(timeout_sec) or timeout_sec <= 0.0:
        raise ValidationError("OpenCL discovery timeout must be positive.")

    def acquire_scope() -> GPUPhysicalSnapshot:
        return acquire_gpu_physical_snapshot(
            command_executor,
            runtime_platform=get_runtime_platform(),
            acquisition_id=f"opencl-runtime-{epoch_ms()}",
        )

    snapshot = await run_joined_thread_call(
        acquire_scope,
        task_name="opencl-runtime-physical-scope",
        retain_resources_until_complete=True,
    )
    return await probe_opencl_runtime(pool, snapshot, timeout_sec=timeout_sec, logger=logger)
