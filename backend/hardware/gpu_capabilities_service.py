"""SoAI - Shared GPU capabilities probing service [backend/hardware/gpu_capabilities_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.singleflight import AsyncSingleflight
from core.concurrency.threading_async import run_sync_in_daemon_thread
from core.di.validation import require_dependencies
from core.errors.exceptions import SoAIError
from core.validation.runtime import is_success_payload
from hardware.gpu_capabilities.aggregate_payloads import build_probe_error_payload
from hardware.probe import sync_get_raw_capabilities
from hardware.vendors.amd.adl_session import AdlRuntime
from hardware.vendors.nvidia.smi import NvidiaSettingsController

if TYPE_CHECKING:
    from core.hardware.protocols import (
        NvidiaCapabilitiesCacheServiceProtocol,
        NvmlGateProtocol,
    )
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict
    from hardware.internal_protocols import (
        GPUInfoCacheServiceProtocol,
        GPUVendorDetectionServiceProtocol,
    )

__all__ = (
    "GpuCapabilitiesService",
    "GpuCapabilitiesServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class GpuCapabilitiesServiceDependencies:
    cache_ttl_seconds: float
    command_executor: CommandExecutorProtocol
    gpu_info_cache_service: GPUInfoCacheServiceProtocol
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol
    nvidia_nvml_gate: NvmlGateProtocol
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol
    nvidia_settings_controller: NvidiaSettingsController | None
    operation: str
    thread_name: str
    logger: TraceLogger
    probe_timeout_seconds: float = 15.0
    adl_runtime: AdlRuntime | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GpuCapabilitiesServiceDependencies",
            cache_ttl_seconds=self.cache_ttl_seconds,
            command_executor=self.command_executor,
            gpu_info_cache_service=self.gpu_info_cache_service,
            gpu_vendor_detection_service=self.gpu_vendor_detection_service,
            logger=self.logger,
            nvidia_capabilities_cache_service=self.nvidia_capabilities_cache_service,
            nvidia_nvml_gate=self.nvidia_nvml_gate,
            operation=self.operation,
            probe_timeout_seconds=self.probe_timeout_seconds,
            thread_name=self.thread_name,
        )


@dataclass(frozen=True, slots=True)
class GPUCapabilitiesObservation:
    payload: JSONDict
    gpu_info_revision: int
    nvidia_revision: int


class GpuCapabilitiesService:

    def __init__(self, deps: GpuCapabilitiesServiceDependencies) -> None:
        self._cache_ttl_seconds = float(deps.cache_ttl_seconds)
        self._executor: CommandExecutorProtocol = deps.command_executor
        self._gpu_info_cache_service: GPUInfoCacheServiceProtocol = deps.gpu_info_cache_service
        self._gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol = (
            deps.gpu_vendor_detection_service
        )
        self._nvidia_nvml_gate: NvmlGateProtocol = deps.nvidia_nvml_gate
        self._nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol = (
            deps.nvidia_capabilities_cache_service
        )
        self._nvidia_settings_controller = deps.nvidia_settings_controller
        self._adl_runtime = deps.adl_runtime
        self._operation = deps.operation
        self._thread_name = deps.thread_name
        self._logger: TraceLogger = deps.logger
        self._probe_timeout_seconds = float(deps.probe_timeout_seconds)
        self._singleflight: AsyncSingleflight[str, GPUCapabilitiesObservation] = AsyncSingleflight()
        self._cache_lock = asyncio.Lock()
        self._cache: JSONDict | None = None
        self._cache_monotonic: float = 0.0
        self._cache_gpu_info_revision: int = self._gpu_info_cache_service.revision()
        self._cache_nvidia_revision = self._nvidia_capabilities_cache_service.revision()
        self._cache_nvidia_expiry = self._nvidia_capabilities_cache_service.expiry_sequence()
        self._worker_active = threading.Event()

    def _cached_sources_are_current(
        self,
        *,
        cache_revision: int,
        gpu_info_revision: int,
        nvidia_revision: int,
        nvidia_expiry: int,
    ) -> bool:
        return (
            cache_revision == gpu_info_revision
            and self._cache_nvidia_revision == nvidia_revision
            and self._cache_nvidia_expiry == nvidia_expiry
        )

    async def get_capabilities(self, enrich_fn: Callable[[JSONDict], JSONDict]) -> JSONDict:
        async with self._cache_lock:
            with (
                self._gpu_info_cache_service.lock,
                self._nvidia_capabilities_cache_service.publication_snapshot() as nvidia_snapshot,
            ):
                if (
                    self._cache is not None
                    and time.monotonic() - self._cache_monotonic < self._cache_ttl_seconds
                    and self._cached_sources_are_current(
                        cache_revision=self._cache_gpu_info_revision,
                        gpu_info_revision=self._gpu_info_cache_service.revision(),
                        nvidia_revision=nvidia_snapshot[0],
                        nvidia_expiry=nvidia_snapshot[1],
                    )
                ):
                    return copy.deepcopy(self._cache)

        async def compute() -> GPUCapabilitiesObservation:
            with (
                self._gpu_info_cache_service.lock,
                self._nvidia_capabilities_cache_service.publication_snapshot() as nvidia_snapshot,
            ):
                probe_revision = self._gpu_info_cache_service.revision()
                nvidia_revision, nvidia_expiry = nvidia_snapshot
            if self._worker_active.is_set():
                return GPUCapabilitiesObservation(
                    build_probe_error_payload(
                        "timeout", "GPU capability recovery is still running."
                    ),
                    probe_revision,
                    nvidia_revision,
                )

            def sync_compute() -> JSONDict:
                self._worker_active.set()
                try:
                    raw = sync_get_raw_capabilities(
                        self._executor,
                        gpu_info_cache_service=self._gpu_info_cache_service,
                        gpu_vendor_detection_service=self._gpu_vendor_detection_service,
                        nvidia_nvml_gate=self._nvidia_nvml_gate,
                        nvidia_capabilities_cache_service=self._nvidia_capabilities_cache_service,
                        logger=self._logger,
                        nvidia_settings_controller=self._nvidia_settings_controller,
                        adl_runtime=self._adl_runtime,
                    )
                    return enrich_fn(raw)
                except TimeoutError:
                    with (
                        self._gpu_info_cache_service.lock,
                        self._nvidia_capabilities_cache_service.publication_snapshot() as snapshot,
                    ):
                        if (
                            self._gpu_info_cache_service.revision() != probe_revision
                            or snapshot[0] != nvidia_revision
                        ):
                            return build_probe_error_payload(
                                "stale_probe", "GPU inventory changed while probing capabilities."
                            )
                    raise
                finally:
                    self._worker_active.clear()

            try:
                payload = await run_sync_in_daemon_thread(
                    sync_compute,
                    timeout=self._probe_timeout_seconds,
                    thread_name=self._thread_name,
                    logger=self._logger,
                    operation=self._operation,
                )
            except TimeoutError:
                return GPUCapabilitiesObservation(
                    build_probe_error_payload(
                        "timeout", "Timed out while probing GPU capabilities."
                    ),
                    probe_revision,
                    nvidia_revision,
                )
            except SoAIError:
                return GPUCapabilitiesObservation(
                    build_probe_error_payload("gpu_error", "GPU capability discovery failed."),
                    probe_revision,
                    nvidia_revision,
                )
            cacheable_payload = (
                isinstance(payload, dict)
                and not isinstance(payload.get("error"), dict)
                and is_success_payload(
                    payload,
                    self._logger,
                    operation="hardware.gpu_capabilities_service.is_success_payload",
                )
            )
            async with self._cache_lock:
                with (
                    self._gpu_info_cache_service.lock,
                    self._nvidia_capabilities_cache_service.publication_snapshot() as nvidia_snapshot,
                ):
                    if (
                        self._gpu_info_cache_service.revision() != probe_revision
                        or nvidia_snapshot[0] != nvidia_revision
                    ):
                        return GPUCapabilitiesObservation(
                            build_probe_error_payload(
                                "stale_probe", "GPU inventory changed while probing capabilities."
                            ),
                            probe_revision,
                            nvidia_revision,
                        )
                    if cacheable_payload and nvidia_snapshot[1] == nvidia_expiry:
                        self._cache = copy.deepcopy(payload)
                        self._cache_monotonic = time.monotonic()
                        self._cache_gpu_info_revision = probe_revision
                        self._cache_nvidia_revision = nvidia_revision
                        self._cache_nvidia_expiry = nvidia_expiry
                    return GPUCapabilitiesObservation(payload, probe_revision, nvidia_revision)

        observation = await self._singleflight.execute_or_wait("gpu_capabilities", compute)
        with (
            self._gpu_info_cache_service.lock,
            self._nvidia_capabilities_cache_service.publication_snapshot() as nvidia_snapshot,
        ):
            if observation.payload.get("success") is True and (
                observation.gpu_info_revision != self._gpu_info_cache_service.revision()
                or observation.nvidia_revision != nvidia_snapshot[0]
            ):
                return build_probe_error_payload(
                    "stale_probe", "GPU inventory changed while probing capabilities."
                )
            return copy.deepcopy(observation.payload)

    async def get_cached_capabilities(self) -> JSONDict | None:
        async with self._cache_lock:
            with (
                self._gpu_info_cache_service.lock,
                self._nvidia_capabilities_cache_service.publication_snapshot() as nvidia_snapshot,
            ):
                if self._cache is None or not self._cached_sources_are_current(
                    cache_revision=self._cache_gpu_info_revision,
                    gpu_info_revision=self._gpu_info_cache_service.revision(),
                    nvidia_revision=nvidia_snapshot[0],
                    nvidia_expiry=nvidia_snapshot[1],
                ):
                    return None
                return copy.deepcopy(self._cache)
