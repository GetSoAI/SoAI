"""SoAI - SoAIBench owned OpenCL child process [backend/hardware/soaibench/opencl_child_main.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import faulthandler
import math
import sys

from core.errors.exceptions import ValidationError
from core.hardware.gpu_physical_identity import GPUPhysicalDevice, GPUPhysicalIdentity
from core.hardware.soaibench_limits import MAX_CHILD_MESSAGE_BYTES
from core.hardware.soaibench_numerical import SoAIBenchNumericalError
from core.hardware.soaibench_workloads import sample_positions
from core.ipc.ndjson import NdjsonCodec
from core.ipc.ndjson_rpc_loop import NdjsonRpcRequest, NdjsonRpcResponse, run_ndjson_rpc_loop
from core.ipc.ndjson_worker_handshake import connect_ndjson_ipc_worker_session
from core.ipc.stream_closing import close_ipc_writer
from core.runtime.event_loop_runner import run_coroutine_in_new_event_loop
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from core.types.json import JSONDict, JSONValue
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.gpu_identity import identity_from_payload
from hardware.soaibench.opencl_child_environment import configure_opencl_child_environment
from hardware.soaibench.opencl_session import OpenCLExecutionSession
from hardware.soaibench.preflight import preflight_blocking
from hardware.soaibench.runtime_discovery import discover_opencl_target
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_alu import execute_alu_workload
from hardware.soaibench.workload_common import SoAIBenchPhaseResult
from hardware.soaibench.workload_compute import execute_compute_workload
from hardware.soaibench.workload_latency import execute_latency_workload
from hardware.soaibench.workload_matrix import execute_matrix_workload
from hardware.soaibench.workload_memory import execute_memory_workload
from hardware.soaibench.workload_mixed import execute_mixed_workload

__all__ = ("main",)


def main() -> None:
    configure_opencl_child_environment()
    faulthandler.enable(file=sys.stderr, all_threads=True)
    run_coroutine_in_new_event_loop(_serve())


async def _serve() -> None:
    codec = NdjsonCodec(
        max_line_bytes=MAX_CHILD_MESSAGE_BYTES, max_depth=32, reject_duplicate_keys=True
    )
    sys.stderr.write("SoAI Bench child stage: authentication\n")
    reader, writer, worker_id = await connect_ndjson_ipc_worker_session(
        worker_label="SoAI Bench", codec=codec
    )
    sys.stderr.write("SoAI Bench child stage: ready\n")
    session: OpenCLExecutionSession | None = None

    async def handle_request(request: NdjsonRpcRequest) -> NdjsonRpcResponse:
        nonlocal session
        response: JSONDict
        try:
            if request.method != "execute":
                raise ValueError("SoAI Bench child method is invalid.")
            command = _read_command(request.payload)
            identity = _command_identity(command)
            sys.stderr.write(
                f"SoAI Bench child stage: {command.get("operation")} {command.get("phase", "")}\n"
            )
            if command.get("operation") == "discover_runtime":
                response = _discover_runtime_command(command, identity)
            else:
                if session is None:
                    session = OpenCLExecutionSession(identity)
                response = _execute(command, session)
        except SoAIBenchUnsupported as exception:
            response = {
                "ok": False,
                "reason": exception.reason,
                "message": exception.message,
            }
            if exception.diagnostic:
                response["diagnostic"] = exception.diagnostic
        except SoAIBenchNumericalError as exception:
            response = {
                "ok": False,
                "reason": "opencl_numerical_mismatch",
                "message": "OpenCL workload numerical validation failed.",
            }
            diagnostic = str(exception)
            if diagnostic:
                response["diagnostic"] = diagnostic[:8192]
        except (
            KeyError,
            IndexError,
            OSError,
            RuntimeError,
            TypeError,
            ValidationError,
            ValueError,
        ) as exception:
            response = {
                "ok": False,
                "reason": "opencl_runtime_error",
                "message": "The SoAI Bench OpenCL child failed while executing its workload.",
            }
            diagnostic = str(exception)
            if diagnostic:
                response["diagnostic"] = diagnostic[:8192]
        return NdjsonRpcResponse(request.request_id, True, response)

    try:
        await run_ndjson_rpc_loop(
            reader=reader,
            writer=writer,
            idle_timeout_sec=INTERACTIVE_TIMEOUT_SEC,
            handle_request=handle_request,
            codec=codec,
        )
    finally:
        try:
            if session is not None:
                session.close()
        finally:
            await close_ipc_writer(writer, worker_id=worker_id)


def _command_identity(command: JSONDict) -> SoAIBenchGpuIdentity:
    identity_payload = command.get("identity")
    if not isinstance(identity_payload, dict):
        raise TypeError("SoAI Bench child command is invalid.")
    return identity_from_payload(identity_payload)


def _read_command(payload: JSONValue) -> JSONDict:
    if not isinstance(payload, dict):
        raise TypeError("SoAI Bench child command is invalid.")
    return payload


def _execute(command: JSONDict, session: OpenCLExecutionSession) -> JSONDict:
    operation = command.get("operation")
    identity_payload = command.get("identity")
    if not isinstance(operation, str) or not isinstance(identity_payload, dict):
        raise TypeError("SoAI Bench child command is invalid.")
    identity = identity_from_payload(identity_payload)
    session.validate_identity(identity)
    if operation == "preflight":
        if set(command) != {"operation", "identity"}:
            raise ValueError("SoAI Bench child preflight fields are invalid.")
        return {"ok": True, "preflight": preflight_blocking(session, identity)}
    if operation != "phase":
        raise ValueError("SoAI Bench child operation is invalid.")
    if set(command) != {"operation", "phase", "stress", "identity"}:
        raise ValueError("SoAI Bench child phase fields are invalid.")
    phase_name = command.get("phase")
    stress = command.get("stress")
    if not isinstance(phase_name, str) or not isinstance(stress, bool):
        raise TypeError("SoAI Bench child phase command is invalid.")
    result = _execute_phase(phase_name, identity, stress, session)
    return {"ok": True, "phase": _phase_payload(result)}


def _execute_phase(
    name: str,
    identity: SoAIBenchGpuIdentity,
    stress: bool,
    session: OpenCLExecutionSession,
) -> SoAIBenchPhaseResult:
    match name:
        case "alu":
            return execute_alu_workload(identity, session)
        case "compute":
            return execute_compute_workload(identity, session)
        case "latency":
            return execute_latency_workload(identity, session)
        case "matrix":
            return execute_matrix_workload(identity, session)
        case "memory":
            return execute_memory_workload(identity, session)
        case "mixed":
            return execute_mixed_workload(identity, stress=stress, session=session)
        case _:
            raise ValueError("SoAI Bench child phase is invalid.")


def _phase_payload(result: SoAIBenchPhaseResult) -> JSONDict:
    if not math.isfinite(result.elapsed_seconds) or result.elapsed_seconds <= 0.0:
        raise ValueError("SoAI Bench child phase timing is invalid.")
    positive_counts = (
        result.duration_ms,
        result.sample_count,
        result.element_count,
        result.rounds,
        result.dispatches,
    )
    if result.checksum < 0 or any(value < 1 for value in positive_counts):
        raise ValueError("SoAI Bench child phase accounting is invalid.")
    if (
        result.sample_positions != sample_positions(result.element_count)
        or len(result.sample_values) != len(result.sample_positions)
        or any(not math.isfinite(value) for value in result.sample_values)
    ):
        raise ValueError("SoAI Bench child phase samples are invalid.")
    return {
        "elapsed_seconds": result.elapsed_seconds,
        "duration_ms": result.duration_ms,
        "checksum": result.checksum,
        "sample_count": result.sample_count,
        "element_count": result.element_count,
        "rounds": result.rounds,
        "dispatches": result.dispatches,
        "summary": result.summary,
        "sample_positions": list(result.sample_positions),
        "sample_values": list(result.sample_values),
    }


def _discover_runtime_command(command: JSONDict, identity: SoAIBenchGpuIdentity) -> JSONDict:
    if set(command) != {"operation", "identity"} or identity.vendor is None:
        raise ValidationError("OpenCL discovery requires the selected physical target.")
    target = GPUPhysicalDevice(
        identity.device_id,
        identity.vendor,
        GPUPhysicalIdentity(identity.gpu_uuid, identity.pci_bdf),
        None,
        None,
        (),
    )
    result = discover_opencl_target(target)
    return {
        "ok": True,
        "runtime": {
            "device_id": result.device_id,
            "vendor": result.vendor,
            "state": result.state.value,
            "reason_code": result.reason_code,
            "message": result.message,
            "match_basis": result.match_basis,
            "platform_name": result.platform_name,
            "driver_version": result.driver_version,
            "effective_uid": result.effective_uid,
            "effective_gid": result.effective_gid,
        },
    }


if __name__ == "__main__":
    main()
