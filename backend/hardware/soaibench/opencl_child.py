"""SoAI - SoAIBench supervised OpenCL child owner [backend/hardware/soaibench/opencl_child.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import math
import sys
from functools import partial
from typing import TYPE_CHECKING, override

from core.concurrency.bounded_blocking import (
    BoundedBlockingCancelledBase,
    BoundedBlockingPool,
    run_bounded_blocking_call,
)
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.pump_lifecycle import close_pump_task
from core.errors.exceptions import (
    ProcessError,
    ServiceUnavailableError,
    SoAIError,
    SoAITimeoutError,
    ValidationError,
)
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.opencl_runtime_types import OpenCLRuntimeTarget
from core.ipc.managed_worker_startup import wait_for_worker_or_exit
from core.ipc.multiplexed import MultiplexedIpcServer
from core.system.async_process_spawning import ManagedAsyncProcess
from core.system.bounded_stream_tail import BoundedStreamTail
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from hardware.soaibench.errors import child_request_failure
from hardware.soaibench.gpu_identity import identity_payload, opencl_target_identity
from hardware.soaibench.internal_protocols import (
    SoAIBenchOpenCLExecutionProtocol,
)
from hardware.soaibench.opencl_child_process import OpenCLChildProcessOwner
from hardware.soaibench.opencl_child_protocol import protocol_error, validate_child_response
from hardware.soaibench.opencl_child_result import (
    phase_result_from_child,
    preflight_result_from_child,
    runtime_result_from_child,
)
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_common import SoAIBenchPhaseResult

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("SoAIBenchOpenCLChild",)

CHILD_CLEANUP_EXCEPTIONS: tuple[type[BaseException], ...] = (
    asyncio.CancelledError,
    *HANDLED_RUNTIME_EXCEPTIONS,
)


class SoAIBenchOpenCLChild(SoAIBenchOpenCLExecutionProtocol):
    def __init__(
        self,
        process: asyncio.subprocess.Process | ManagedAsyncProcess,
        logger: LoggerProtocol,
        numerical_validation_pool: BoundedBlockingPool,
        server: MultiplexedIpcServer,
        worker_id: int,
        diagnostic_streams: tuple[tuple[BoundedStreamTail, asyncio.Task[None]], ...],
        *,
        cleanup_pool: BoundedBlockingPool | None = None,
        startup_allowance_seconds: float = 0.0,
    ) -> None:
        self._process_owner = OpenCLChildProcessOwner(process, logger, cleanup_pool=cleanup_pool)
        self._startup_allowance_seconds = startup_allowance_seconds
        self._logger = logger
        self._numerical_validation_pool = numerical_validation_pool
        self._request_lock = asyncio.Lock()
        self._execution_lock = asyncio.Lock()
        self._unavailable = False
        self._server = server
        self._worker_id = worker_id
        self._request_sequence = 0
        self._diagnostic_streams = diagnostic_streams
        self._request_failure: SoAIError | None = None

    @override
    async def discover_runtime(
        self, target: GPUPhysicalDevice, *, timeout_sec: float
    ) -> OpenCLRuntimeTarget:
        async with self._execution_lock:
            response = await self._request(
                {
                    "operation": "discover_runtime",
                    "identity": identity_payload(opencl_target_identity(target)),
                },
                timeout_sec=timeout_sec,
            )
            payload = response.get("runtime")
            if not isinstance(payload, dict):
                self._unavailable = True
                raise protocol_error("The OpenCL child returned invalid discovery data.")
            try:
                result = runtime_result_from_child(payload)
                if result.device_id != target.device_id or result.vendor != target.vendor:
                    raise protocol_error("The OpenCL child changed its selected physical target.")
                return result
            except ProcessError:
                self._unavailable = True
                raise

    @override
    async def preflight(
        self,
        identity: SoAIBenchGpuIdentity,
        *,
        timeout_sec: float,
    ) -> JSONDict:
        async with self._execution_lock:
            response = await self._request(
                {
                    "operation": "preflight",
                    "identity": identity_payload(identity),
                },
                timeout_sec=timeout_sec,
            )
            payload = response.get("preflight")
            if not isinstance(payload, dict):
                self._unavailable = True
                raise protocol_error("The OpenCL child returned invalid preflight data.")
            try:
                return preflight_result_from_child(payload)
            except ProcessError:
                self._unavailable = True
                raise

    @override
    async def phase(
        self,
        name: str,
        identity: SoAIBenchGpuIdentity,
        *,
        stress: bool,
        timeout_sec: float,
    ) -> SoAIBenchPhaseResult:
        async with self._execution_lock:
            response = await self._request(
                {
                    "operation": "phase",
                    "phase": name,
                    "stress": stress,
                    "identity": identity_payload(identity),
                },
                timeout_sec=timeout_sec,
            )
            payload = response.get("phase")
            if not isinstance(payload, dict):
                self._unavailable = True
                raise protocol_error("The OpenCL child returned invalid phase data.")
            try:
                return await run_bounded_blocking_call(
                    self._numerical_validation_pool,
                    partial(phase_result_from_child, payload, name, stress=stress),
                )
            except BoundedBlockingCancelledBase as exception:
                self._unavailable = True
                try:
                    await uncancel_then_cleanup(exception.wait_for_completion(None))
                except ProcessError as cleanup_exception:
                    raise asyncio.CancelledError() from cleanup_exception
                raise asyncio.CancelledError() from exception
            except ProcessError:
                self._unavailable = True
                raise

    @override
    async def close(self) -> None:
        self._unavailable = True
        try:
            try:
                await self._server.disconnect_worker(self._worker_id)
            finally:
                await self._process_owner.close()
        finally:
            try:
                await self._server.forget_worker_secret(self._worker_id)
            finally:
                primary_exception = sys.exception()
                cleanup_failure: BaseException | None = None
                for _tail, pump in self._diagnostic_streams:
                    try:
                        await uncancel_then_cleanup(
                            close_pump_task(
                                pump,
                                timeout_seconds=float(RESPONSIVE_TIMEOUT_SEC),
                                logger=self._logger,
                                timeout_message="SoAI Bench diagnostic stream did not close before its deadline.",
                            )
                        )
                    except CHILD_CLEANUP_EXCEPTIONS as exception:
                        if cleanup_failure is None:
                            cleanup_failure = exception
                        else:
                            cleanup_failure.add_note(
                                f"Additional diagnostic stream cleanup failed: {exception}"
                            )
                if self._request_failure is not None and self._request_failure.details is not None:
                    if self._process_owner.closed:
                        self._request_failure.details["return_code"] = (
                            self._process_owner.process.process.returncode
                            if isinstance(self._process_owner.process, ManagedAsyncProcess)
                            else self._process_owner.process.returncode
                        )
                    self._request_failure.details["diagnostics"] = [
                        tail.diagnostic() for tail, _pump in self._diagnostic_streams
                    ]
                    self._request_failure.details["diagnostics_complete"] = (
                        cleanup_failure is None
                        and all(
                            pump.done() and not pump.cancelled() and pump.exception() is None
                            for _tail, pump in self._diagnostic_streams
                        )
                    )
                if cleanup_failure is not None:
                    if primary_exception is None:
                        raise cleanup_failure
                    primary_exception.add_note(
                        f"Diagnostic stream cleanup also failed: {cleanup_failure}"
                    )

    @property
    @override
    def degraded(self) -> bool:
        return self._process_owner.degraded

    @property
    def exit_verified(self) -> bool:
        return self._process_owner.closed

    async def _request(self, command: JSONDict, *, timeout_sec: float) -> JSONDict:
        if not math.isfinite(timeout_sec) or timeout_sec <= 0.0:
            raise ValidationError("SoAI Bench child timeout must be positive.")
        async with self._request_lock:
            if self._process_owner.closed or self._process_owner.degraded or self._unavailable:
                raise ProcessError(
                    "SoAI Bench OpenCL child is unavailable.",
                    details={"failure_type": "disconnected"},
                )
            self._request_sequence += 1
            request_id = f"soaibench:{self._worker_id}:{self._request_sequence}"
            request_timeout_sec = timeout_sec + self._startup_allowance_seconds
            startup_timeout_sec = min(timeout_sec, 60.0) + self._startup_allowance_seconds
            during_startup = True
            try:
                async with asyncio.timeout(request_timeout_sec):
                    await wait_for_worker_or_exit(
                        self._server,
                        worker_id=self._worker_id,
                        process=self._process_owner.process,
                        diagnostic_log_path="",
                        startup_timeout_sec=startup_timeout_sec,
                    )
                    self._startup_allowance_seconds = 0.0
                    during_startup = False
                    envelope = await self._server.request(
                        self._worker_id,
                        method="execute",
                        request_id=request_id,
                        payload=command,
                        timeout_sec=request_timeout_sec,
                        disconnect_on_cancel=True,
                    )
                payload = envelope.get("payload")
                if envelope.get("ok") is not True or not isinstance(payload, dict):
                    raise protocol_error("SoAI Bench OpenCL child response is invalid.")
                return validate_child_response(payload, self._logger)
            except asyncio.CancelledError:
                self._unavailable = True
                raise
            except (
                SoAITimeoutError,
                OSError,
                ValueError,
                ValidationError,
                ServiceUnavailableError,
                ProcessError,
            ) as exception:
                self._unavailable = True
                self._request_failure = child_request_failure(
                    exception,
                    during_startup=during_startup,
                    details={
                        "worker_id": self._worker_id,
                        "request_id": request_id,
                        "operation": command.get("operation"),
                        "phase": command.get("phase"),
                        "deadline_seconds": request_timeout_sec,
                        "configured_deadline_seconds": timeout_sec,
                        "startup_allowance_seconds": request_timeout_sec - timeout_sec,
                        "startup_deadline_seconds": startup_timeout_sec,
                        "return_code": (
                            self._process_owner.process.process.returncode
                            if isinstance(self._process_owner.process, ManagedAsyncProcess)
                            else self._process_owner.process.returncode
                        ),
                        "diagnostics": [
                            tail.diagnostic() for tail, _pump in self._diagnostic_streams
                        ],
                    },
                )
                if self._request_failure is exception:
                    raise
                raise self._request_failure from exception
