"""SoAI - Whole-request native backend preflight and member routing [backend/hardware/gpu_tuning/native_backend_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_control_operation_types import GPUControlPreflightRejection
from core.hardware.gpu_control_types import GPUControlMemberInvocation, GPUPreparedControl
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.hardware.protocols import GPUControlRecoveryProtocol
from core.system.protocols import CommandExecutorProtocol
from hardware.gpu_tuning.control_recovery_records import recovery_member_key
from hardware.gpu_tuning.native_control_results import build_native_member_result
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.vendors.amd.adl_session import AdlSession
from hardware.vendors.amd.adl_settings import (
    invoke_adl_prepared_member,
    preflight_adl_control_record,
)
from hardware.vendors.amd.member_execution import (
    invoke_amd_prepared_member,
    preflight_amd_control_record,
)
from hardware.vendors.intel.member_execution import (
    invoke_intel_prepared_member,
    preflight_intel_control_record,
)
from hardware.vendors.nvidia.internal_protocols import (
    NvmlControlModuleProtocol,
    NvmlNativeFunctionResolverProtocol,
)
from hardware.vendors.nvidia.nvapi_control_preparation import preflight_nvapi_control_record
from hardware.vendors.nvidia.nvapi_member_execution import invoke_nvapi_prepared_member
from hardware.vendors.nvidia.nvml_member_execution import (
    invoke_nvml_prepared_member,
    preflight_nvml_control_record,
)
from hardware.vendors.nvidia.settings_control_queries import NvidiaSettingsSession
from hardware.vendors.nvidia.settings_member_execution import (
    invoke_settings_prepared_member,
    preflight_settings_control_record,
)

if TYPE_CHECKING:
    from core.hardware.gpu_recovery_records import GPUControlMemberKey

__all__ = ("NativeBackendExecution",)


@dataclass(frozen=True, slots=True)
class NativeBackendExecution:
    executor: CommandExecutorProtocol
    gpu_services: GpuServiceDependencies
    nvml_module: NvmlControlModuleProtocol | None
    resolver: NvmlNativeFunctionResolverProtocol | None
    query_interface: Callable[[int], int | None] | None
    settings_session: NvidiaSettingsSession | None
    goal: Literal["requested", "original"]
    adl_session: AdlSession | None = None

    def __post_init__(self) -> None:
        if self.goal not in ("requested", "original"):
            raise ValidationError("Native execution requires its explicit immutable goal.")

    def preflight(
        self, record: GPURecoveryRecord, prepared: GPUPreparedControl
    ) -> tuple[GPUControlPreflightRejection | None, tuple[Exception, ...]]:
        if self.goal == "original":
            return None, ()
        acquired: set[str] = set()
        for member in record.members:
            backend = member.backend
            route = "amd" if backend in ("amd_smi", "amd_overdrive") else backend
            if route in acquired:
                continue
            rejection, failures = self._preflight_backend(backend, record, prepared)
            if rejection is not None or failures:
                return rejection, failures
            if route is not None:
                acquired.add(route)
        return None, ()

    def _preflight_backend(
        self, backend: str | None, record: GPURecoveryRecord, prepared: GPUPreparedControl
    ) -> tuple[GPUControlPreflightRejection | None, tuple[Exception, ...]]:
        if backend == "nvml":
            if self.nvml_module is None:
                return self._unavailable("NVML module acquisition is unavailable.")
            return preflight_nvml_control_record(
                self.nvml_module, record, prepared, resolver=self.resolver, goal=self.goal
            )
        if backend == "nvapi":
            if self.query_interface is None:
                return self._unavailable("NvAPI native QueryInterface acquisition is unavailable.")
            return preflight_nvapi_control_record(
                self.executor,
                record,
                prepared,
                executable=self.gpu_services.nvidia_smi_executable,
                query_interface=self.query_interface,
                nvml_module=self.nvml_module,
                goal=self.goal,
            )
        if backend == "nvidia_settings":
            if self.settings_session is None:
                return self._unavailable("NVIDIA settings actual display session is unavailable.")
            return preflight_settings_control_record(
                self.settings_session, record, prepared, goal=self.goal
            )
        if backend == "amd_adl":
            if self.adl_session is None:
                return self._unavailable("ADL native session acquisition is unavailable.")
            return preflight_adl_control_record(self.adl_session, self.executor, record, prepared)
        if backend in ("amd_smi", "amd_overdrive"):
            return preflight_amd_control_record(self.executor, record, prepared, goal=self.goal)
        if backend in ("intel_xpum", "intel_i915"):
            return preflight_intel_control_record(
                self.executor,
                executable=self.gpu_services.intel_executable,
                record=record,
                prepared=prepared,
                goal=self.goal,
            )
        return (
            GPUControlPreflightRejection(
                "native_control_unsupported", "The frozen native backend has no control owner."
            ),
            (),
        )

    def invoke_member(
        self,
        record: GPURecoveryRecord,
        prepared: GPUPreparedControl,
        recovery: GPUControlRecoveryProtocol,
        token: CancellationTokenProtocol,
        member: GPURecoveryMember,
    ) -> GPUControlMemberInvocation:
        if member not in record.members:
            raise ValidationError("Native dispatch requires the exact frozen selected member.")
        if member.backend == "nvml" and self.nvml_module is not None:
            return invoke_nvml_prepared_member(
                self.nvml_module,
                record,
                prepared,
                recovery,
                token,
                member,
                self.resolver,
                self.goal,
            )
        if member.backend == "nvapi" and self.query_interface is not None:
            return invoke_nvapi_prepared_member(
                self.executor,
                record,
                prepared,
                recovery,
                token,
                member,
                executable=self.gpu_services.nvidia_smi_executable,
                query_interface=self.query_interface,
                nvml_module=self.nvml_module,
                goal=self.goal,
            )
        if member.backend == "nvidia_settings" and self.settings_session is not None:
            return invoke_settings_prepared_member(
                self.settings_session, record, prepared, recovery, token, member, goal=self.goal
            )
        if member.backend == "amd_adl" and self.adl_session is not None:
            return invoke_adl_prepared_member(
                self.adl_session,
                self.executor,
                record,
                prepared,
                recovery,
                token,
                member,
                goal=self.goal,
            )
        if member.backend in ("amd_smi", "amd_overdrive"):
            return invoke_amd_prepared_member(
                self.executor, record, prepared, recovery, token, member, goal=self.goal
            )
        if member.backend in ("intel_xpum", "intel_i915"):
            return invoke_intel_prepared_member(
                self.executor,
                executable=self.gpu_services.intel_executable,
                runtime_platform=self.gpu_services.nvidia_nvml_gate.runtime_platform,
                record=record,
                prepared=prepared,
                recovery=recovery,
                token=token,
                member=member,
                goal=self.goal,
            )
        if self.goal == "original":
            return GPUControlMemberInvocation(
                prepared,
                (
                    build_native_member_result(
                        member, None, False, "native_query_failed", "original"
                    ),
                ),
                (),
                False,
            )
        raise StateError("The preflighted native member resource is unavailable at dispatch.")

    def original_member_order(self, record: GPURecoveryRecord) -> tuple[GPUControlMemberKey, ...]:
        leading = tuple(
            member
            for member in record.members
            if member.backend == "nvidia_settings" and member.member_id == "gpu_fan_policy"
        )
        deferred = tuple(
            member
            for member in record.members
            if (member.backend, member.field)
            in (("nvml", "persistence_mode"), ("amd_overdrive", "performance_mode"))
        )
        members = (
            leading
            + tuple(
                member
                for member in record.members
                if member not in leading and member not in deferred
            )
            + deferred
        )
        return tuple(recovery_member_key(member) for member in members)

    @staticmethod
    def _unavailable(diagnostic: str) -> tuple[GPUControlPreflightRejection, tuple[Exception, ...]]:
        return GPUControlPreflightRejection("native_query_failed", diagnostic), ()
