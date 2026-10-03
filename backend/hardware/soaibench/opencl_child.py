"""SoAI - SoAIBench supervised OpenCL child owner [backend/hardware/soaibench/opencl_child.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import math
import os
import subprocess
import sys
from functools import partial
from typing import TYPE_CHECKING, override

from core.concurrency.bounded_blocking import (
    BoundedBlockingCancelledBase,
    BoundedBlockingPool,
    run_bounded_blocking_call,
)
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import ProcessError, ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from core.system.async_process_spawning import spawn_async_process
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.gpu_identity import identity_payload
from hardware.soaibench.internal_protocols import (
    MAX_CHILD_MESSAGE_BYTES,
    SoAIBenchOpenCLExecutionProtocol,
)
from hardware.soaibench.opencl_child_process import OpenCLChildProcessOwner
from hardware.soaibench.opencl_child_result import (
    phase_result_from_child,
    preflight_result_from_child,
)
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_common import SoAIBenchPhaseResult

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("SoAIBenchOpenCLChild", "spawn_soaibench_opencl_child")

CHILD_OPERATION = "hardware.soaibench.opencl_child"


class SoAIBenchOpenCLChild(SoAIBenchOpenCLExecutionProtocol):
    def __init__(
        self,
        process: asyncio.subprocess.Process,
        logger: LoggerProtocol,
        numerical_validation_pool: BoundedBlockingPool,
    ) -> None:
        self._process_owner = OpenCLChildProcessOwner(process, logger)
        self._logger = logger
        self._numerical_validation_pool = numerical_validation_pool
        self._request_lock = asyncio.Lock()
        self._unavailable = False

    @override
    async def preflight(
        self,
        identity: SoAIBenchGpuIdentity,
        *,
        timeout_sec: float,
    ) -> JSONDict:
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
            raise self._protocol_error("The OpenCL child returned invalid preflight data.")
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
            raise self._protocol_error("The OpenCL child returned invalid phase data.")
        try:
            return await run_bounded_blocking_call(
                self._numerical_validation_pool,
                partial(phase_result_from_child, payload, name, stress=stress),
            )
        except BoundedBlockingCancelledBase as exception:
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
        await self._process_owner.close()

    @property
    @override
    def degraded(self) -> bool:
        return self._process_owner.degraded

    @property
    def exit_verified(self) -> bool:
        return self._process_owner.closed

    async def _request(self, command: JSONDict, *, timeout_sec: float) -> JSONDict:
        if self._process_owner.closed or self._process_owner.degraded or self._unavailable:
            raise ProcessError("SoAIBench OpenCL child is unavailable.", operation=CHILD_OPERATION)
        if not math.isfinite(timeout_sec) or timeout_sec <= 0.0:
            raise ValidationError("SoAIBench child timeout must be positive.")
        async with self._request_lock:
            process = self._process_owner.process
            if process.stdin is None or process.stdout is None:
                raise self._protocol_error("SoAIBench OpenCL child pipes are unavailable.")
            encoded = serialize_json_compact_stable(command).encode("utf-8") + b"\n"
            if len(encoded) > MAX_CHILD_MESSAGE_BYTES:
                raise self._protocol_error("SoAIBench OpenCL child command is too large.")
            try:
                async with asyncio.timeout(timeout_sec):
                    process.stdin.write(encoded)
                    await process.stdin.drain()
                    line = await process.stdout.readline()
            except asyncio.CancelledError:
                self._unavailable = True
                raise
            except TimeoutError as exception:
                self._unavailable = True
                raise ProcessError(
                    "SoAIBench OpenCL child exceeded its deadline.",
                    operation=CHILD_OPERATION,
                    cause=exception,
                ) from exception
            except (OSError, ValueError) as exception:
                self._unavailable = True
                raise ProcessError(
                    "SoAIBench OpenCL child connection failed.",
                    operation=CHILD_OPERATION,
                    cause=exception,
                ) from exception
            if not line:
                self._unavailable = True
                raise self._protocol_error("SoAIBench OpenCL child exited without a result.")
            if len(line) > MAX_CHILD_MESSAGE_BYTES:
                self._unavailable = True
                raise self._protocol_error("SoAIBench OpenCL child response is too large.")
            try:
                parsed = parse_json_value(
                    line,
                    field="SoAIBench OpenCL child response",
                    max_depth=32,
                    strict_utf8=True,
                    reject_duplicate_keys=True,
                )
            except ValidationError as exception:
                self._unavailable = True
                raise self._protocol_error(
                    "SoAIBench OpenCL child response is invalid."
                ) from exception
            if not isinstance(parsed, dict):
                self._unavailable = True
                raise self._protocol_error("SoAIBench OpenCL child response is not an object.")
            response = parsed
            try:
                return self._validate_response(response)
            except ProcessError:
                self._unavailable = True
                raise

    def _validate_response(self, response: JSONDict) -> JSONDict:
        if response.get("ok") is True:
            if set(response) not in ({"ok", "preflight"}, {"ok", "phase"}):
                raise self._protocol_error("SoAIBench OpenCL child response fields are invalid.")
            return response
        if response.get("ok") is not False:
            raise self._protocol_error("SoAIBench OpenCL child response status is invalid.")
        reason = response.get("reason")
        message = response.get("message")
        diagnostic = response.get("diagnostic")
        if set(response) not in (
            {"ok", "reason", "message"},
            {"ok", "reason", "message", "diagnostic"},
        ):
            raise self._protocol_error("SoAIBench OpenCL child failure fields are invalid.")
        failure_fields = _validated_failure_fields(reason, message, diagnostic)
        if failure_fields is None:
            raise self._protocol_error("SoAIBench OpenCL child failure is invalid.")
        reason_text, message_text, diagnostic_text = failure_fields
        if diagnostic_text is not None:
            self._logger.error(
                "SoAIBench OpenCL child diagnostic for %s: %s",
                reason_text,
                diagnostic_text,
            )
        raise SoAIBenchUnsupported(reason_text, message_text)

    @staticmethod
    def _protocol_error(message: str) -> ProcessError:
        return ProcessError(message, operation=CHILD_OPERATION)


async def spawn_soaibench_opencl_child(
    logger: LoggerProtocol,
    numerical_validation_pool: BoundedBlockingPool,
) -> SoAIBenchOpenCLChild:
    process = await spawn_async_process(
        [sys.executable, "-m", "hardware.soaibench.opencl_child_main"],
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name != "nt",
        limit=MAX_CHILD_MESSAGE_BYTES,
    )
    return SoAIBenchOpenCLChild(process, logger, numerical_validation_pool)


def _bounded_text(value: str) -> bool:
    return 0 < len(value.encode("utf-8")) <= MAX_CHILD_MESSAGE_BYTES


def _validated_failure_fields(
    reason: JSONValue,
    message: JSONValue,
    diagnostic: JSONValue,
) -> tuple[str, str, str | None] | None:
    if not isinstance(reason, str) or not _bounded_text(reason):
        return None
    if not isinstance(message, str) or not _bounded_text(message):
        return None
    if diagnostic is not None and (
        not isinstance(diagnostic, str) or not _bounded_text(diagnostic)
    ):
        return None
    return reason, message, diagnostic
