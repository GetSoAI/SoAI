"""SoAI - SoAIBench owned OpenCL child process [backend/hardware/soaibench/opencl_child_main.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import sys

from core.errors.exceptions import ValidationError
from core.hardware.soaibench_numerical import SoAIBenchNumericalError
from core.hardware.soaibench_workloads import sample_positions
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONDict
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.gpu_identity import identity_from_payload
from hardware.soaibench.internal_protocols import MAX_CHILD_MESSAGE_BYTES
from hardware.soaibench.opencl_session import OpenCLExecutionSession
from hardware.soaibench.preflight import preflight_blocking
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
    session: OpenCLExecutionSession | None = None
    try:
        for line in sys.stdin.buffer:
            response: JSONDict
            try:
                command = _read_command(line)
                identity = _command_identity(command)
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
                    "message": "The SoAIBench OpenCL child failed while executing its workload.",
                }
                diagnostic = str(exception)
                if diagnostic:
                    response["diagnostic"] = diagnostic[:8192]
            _write_response(response)
    finally:
        if session is not None:
            session.close()


def _command_identity(command: JSONDict) -> SoAIBenchGpuIdentity:
    identity_payload = command.get("identity")
    if not isinstance(identity_payload, dict):
        raise TypeError("SoAIBench child command is invalid.")
    return identity_from_payload(identity_payload)


def _read_command(line: bytes) -> JSONDict:
    if len(line) > MAX_CHILD_MESSAGE_BYTES:
        raise ValueError("SoAIBench child command is too large.")
    try:
        parsed = parse_json_value(
            line,
            field="SoAIBench child command",
            max_depth=32,
            strict_utf8=True,
            reject_duplicate_keys=True,
        )
    except (TypeError, ValueError) as exception:
        raise ValueError("SoAIBench child command is invalid.") from exception
    if not isinstance(parsed, dict):
        raise TypeError("SoAIBench child command is invalid.")
    return parsed


def _execute(command: JSONDict, session: OpenCLExecutionSession) -> JSONDict:
    operation = command.get("operation")
    identity_payload = command.get("identity")
    if not isinstance(operation, str) or not isinstance(identity_payload, dict):
        raise TypeError("SoAIBench child command is invalid.")
    identity = identity_from_payload(identity_payload)
    session.validate_identity(identity)
    if operation == "preflight":
        if set(command) != {"operation", "identity"}:
            raise ValueError("SoAIBench child preflight fields are invalid.")
        return {"ok": True, "preflight": preflight_blocking(identity)}
    if operation != "phase":
        raise ValueError("SoAIBench child operation is invalid.")
    if set(command) != {"operation", "phase", "stress", "identity"}:
        raise ValueError("SoAIBench child phase fields are invalid.")
    phase_name = command.get("phase")
    stress = command.get("stress")
    if not isinstance(phase_name, str) or not isinstance(stress, bool):
        raise TypeError("SoAIBench child phase command is invalid.")
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
            raise ValueError("SoAIBench child phase is invalid.")


def _phase_payload(result: SoAIBenchPhaseResult) -> JSONDict:
    if not math.isfinite(result.elapsed_seconds) or result.elapsed_seconds <= 0.0:
        raise ValueError("SoAIBench child phase timing is invalid.")
    positive_counts = (
        result.duration_ms,
        result.sample_count,
        result.element_count,
        result.rounds,
        result.dispatches,
    )
    if result.checksum < 0 or any(value < 1 for value in positive_counts):
        raise ValueError("SoAIBench child phase accounting is invalid.")
    if (
        result.sample_positions != sample_positions(result.element_count)
        or len(result.sample_values) != len(result.sample_positions)
        or any(not math.isfinite(value) for value in result.sample_values)
    ):
        raise ValueError("SoAIBench child phase samples are invalid.")
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


def _write_response(response: JSONDict) -> None:
    try:
        encoded = serialize_json_compact_stable(response).encode("utf-8")
    except (TypeError, ValueError):
        encoded = _failure_response_bytes()
    if len(encoded) + 1 > MAX_CHILD_MESSAGE_BYTES:
        encoded = _failure_response_bytes()
    sys.stdout.buffer.write(encoded + b"\n")
    sys.stdout.buffer.flush()


def _failure_response_bytes() -> bytes:
    return (
        b'{"ok":false,"reason":"opencl_runtime_error",'
        b'"message":"The SoAIBench OpenCL child response exceeded its size bound."}'
    )


if __name__ == "__main__":
    main()
