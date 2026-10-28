"""SoAI - SoAIBench child result validation [backend/hardware/soaibench/opencl_child_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exceptions import ValidationError
from core.hardware.opencl_runtime_types import OpenCLRuntimeState, OpenCLRuntimeTarget
from core.hardware.soaibench_evidence import PhaseAccounting, minimum_measured_duration_ms
from core.hardware.soaibench_numerical import validate_sample_values
from core.hardware.soaibench_workloads import (
    ELEMENT_ALIGNMENT,
    MAX_COMPLETED_DISPATCHES,
    MINIMUM_PHASE_SECONDS,
    sample_positions,
    workload_spec,
)
from core.types.json import JSONDict, JSONValue
from core.validation.requirements import (
    require_non_negative_exact_int,
    require_positive_exact_int,
)
from core.validation.strict_numbers import require_finite_float_strict
from hardware.soaibench.device_matching import STRONG_MATCH_BASES
from hardware.soaibench.opencl_child_metadata import (
    bounded_child_nonempty_text,
    bounded_child_optional_text,
    validate_child_capability_evidence,
    validate_child_device_metadata,
)
from hardware.soaibench.opencl_child_protocol import protocol_error
from hardware.soaibench.workload_common import SoAIBenchPhaseResult

__all__ = ("phase_result_from_child", "preflight_result_from_child", "runtime_result_from_child")

PREFLIGHT_FIELDS = (
    "match_basis",
    "queue_api",
    "opencl_platform_name",
    "opencl_platform_vendor",
    "opencl_device_name",
    "opencl_device_vendor",
    "opencl_driver_version",
    "opencl_enumeration_warnings",
)


def preflight_result_from_child(payload: JSONDict) -> JSONDict:
    if set(payload) not in (set(PREFLIGHT_FIELDS), {*PREFLIGHT_FIELDS, "opencl"}):
        raise protocol_error("SoAI Bench child preflight fields are invalid.")
    validate_child_device_metadata(payload)
    if "opencl" in payload:
        validate_child_capability_evidence(payload["opencl"])
    warnings = payload.get("opencl_enumeration_warnings")
    if (
        not isinstance(warnings, list)
        or len(warnings) > 32
        or any(
            not isinstance(warning, str) or not warning or len(warning) > 128
            for warning in warnings
        )
    ):
        raise protocol_error("SoAI Bench child OpenCL enumeration warnings are invalid.")
    return payload


def phase_result_from_child(
    payload: JSONDict,
    name: str,
    *,
    stress: bool,
) -> SoAIBenchPhaseResult:
    required_fields = {
        "elapsed_seconds",
        "duration_ms",
        "checksum",
        "sample_count",
        "element_count",
        "rounds",
        "dispatches",
        "summary",
        "sample_positions",
        "sample_values",
    }
    if set(payload) != required_fields:
        raise protocol_error("SoAI Bench child phase fields are invalid.")
    positions_value = payload.get("sample_positions")
    samples_value = payload.get("sample_values")
    if not isinstance(positions_value, list) or not isinstance(samples_value, list):
        raise protocol_error("SoAI Bench child phase samples are invalid.")
    element_count = _positive_integer(payload, "element_count")
    if positions_value != list(sample_positions(element_count)) or len(samples_value) != 64:
        raise protocol_error(f"SoAI Bench child {name} phase sample boundaries are invalid.")
    try:
        positions = tuple(
            require_non_negative_exact_int(
                value,
                type_message="SoAI Bench child sample position is invalid.",
                range_message="SoAI Bench child sample position is invalid.",
            )
            for value in positions_value
        )
        samples = tuple(
            require_finite_float_strict(
                value,
                error_message="SoAI Bench child sample value is invalid.",
            )
            for value in samples_value
        )
    except ValidationError as exception:
        raise protocol_error(str(exception)) from exception
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise protocol_error("SoAI Bench child phase summary is invalid.")
    result = SoAIBenchPhaseResult(
        elapsed_seconds=_positive_number(payload, "elapsed_seconds"),
        duration_ms=_positive_integer(payload, "duration_ms"),
        checksum=_positive_integer(payload, "checksum"),
        sample_count=_positive_integer(payload, "sample_count"),
        element_count=element_count,
        rounds=_positive_integer(payload, "rounds"),
        dispatches=_positive_integer(payload, "dispatches"),
        summary=summary,
        sample_positions=positions,
        sample_values=samples,
    )
    _validate_phase_result(result, name, stress=stress)
    _validate_summary(result, name, stress=stress)
    return result


def _validate_phase_result(
    result: SoAIBenchPhaseResult,
    name: str,
    *,
    stress: bool,
) -> None:
    try:
        spec = workload_spec(name, stress=stress)
        elements_valid = (
            result.element_count == spec.maximum_elements
            if spec.exact_elements
            else spec.minimum_elements <= result.element_count <= spec.maximum_elements
            and result.element_count % ELEMENT_ALIGNMENT == 0
        )
        if result.elapsed_seconds < MINIMUM_PHASE_SECONDS:
            raise ValueError("SoAI Bench child phase elapsed time is invalid.")
        if result.rounds != spec.rounds:
            raise ValueError("SoAI Bench child phase rounds are invalid.")
        if not elements_valid:
            raise ValueError("SoAI Bench child phase element count is invalid.")
        if (
            result.dispatches > MAX_COMPLETED_DISPATCHES
            or result.dispatches < spec.batch_dispatches
            or result.dispatches % spec.batch_dispatches != 0
        ):
            raise ValueError("SoAI Bench child phase dispatch count is invalid.")
        if result.sample_count != result.dispatches:
            raise ValueError("SoAI Bench child phase sample count is invalid.")
        minimum_duration_ms = minimum_measured_duration_ms(
            (
                PhaseAccounting(
                    result.elapsed_seconds,
                    result.element_count,
                    result.rounds,
                    result.dispatches,
                ),
            )
        )
        if result.duration_ms < minimum_duration_ms:
            raise ValueError("SoAI Bench child phase duration is invalid.")
        validate_sample_values(
            name,
            result.element_count,
            result.rounds,
            result.dispatches,
            result.sample_positions,
            result.sample_values,
            stress=stress,
        )
    except ValueError as exception:
        raise protocol_error(str(exception)) from exception


def _positive_integer(payload: Mapping[str, JSONValue], field: str) -> int:
    try:
        return require_positive_exact_int(
            payload.get(field),
            type_message=f"SoAI Bench child {field} is invalid.",
            range_message=f"SoAI Bench child {field} is invalid.",
        )
    except ValidationError as exception:
        raise protocol_error(str(exception)) from exception


def _positive_number(payload: Mapping[str, JSONValue], field: str) -> float:
    try:
        value = require_finite_float_strict(
            payload.get(field),
            error_message=f"SoAI Bench child {field} is invalid.",
        )
    except ValidationError as exception:
        raise protocol_error(str(exception)) from exception
    if value <= 0.0:
        raise protocol_error(f"SoAI Bench child {field} is invalid.")
    return value


def _validate_summary(
    result: SoAIBenchPhaseResult,
    name: str,
    *,
    stress: bool,
) -> None:
    prefix = f"{name}_"
    expected_integers = {
        f"{prefix}checksum": result.checksum,
        f"{prefix}elements": result.element_count,
        f"{prefix}requested_elements": workload_spec(name, stress=stress).maximum_elements,
        f"{prefix}allocation_bytes": result.element_count * 4,
        f"{prefix}checksum_sample_count": 64,
    }
    required_fields = {
        *expected_integers,
        f"{prefix}native_dispatch_elements",
        "queue_api",
        "match_basis",
        "opencl_platform_name",
        "opencl_platform_vendor",
        "opencl_device_name",
        "opencl_device_vendor",
        "opencl_driver_version",
        "opencl_global_mem_bytes",
        "opencl_max_alloc_bytes",
    }
    if set(result.summary) != required_fields:
        raise protocol_error("SoAI Bench child phase summary fields are invalid.")
    if any(result.summary.get(field) != value for field, value in expected_integers.items()) or (
        result.summary.get(f"{prefix}native_dispatch_elements")
        not in {ELEMENT_ALIGNMENT, result.element_count}
    ):
        raise protocol_error("SoAI Bench child phase summary values are invalid.")
    for field in ("opencl_global_mem_bytes", "opencl_max_alloc_bytes"):
        _positive_integer(result.summary, field)
    validate_child_device_metadata(result.summary)


def runtime_result_from_child(payload: JSONDict) -> OpenCLRuntimeTarget:
    fields = (
        "device_id",
        "vendor",
        "state",
        "reason_code",
        "message",
        "match_basis",
        "platform_name",
        "driver_version",
        "effective_uid",
        "effective_gid",
    )
    if set(payload) != set(fields):
        raise protocol_error("OpenCL discovery result fields are invalid.")
    try:
        state = OpenCLRuntimeState(bounded_child_nonempty_text(payload.get("state"), "state"))
        device_id = bounded_child_nonempty_text(payload.get("device_id"), "device_id")
        vendor = bounded_child_nonempty_text(payload.get("vendor"), "vendor")
        message = bounded_child_optional_text(payload.get("message"), "message")
        texts = tuple(
            (
                None
                if payload.get(field) is None
                else bounded_child_optional_text(payload.get(field), field)
            )
            for field in ("reason_code", "match_basis", "platform_name", "driver_version")
        )
        accounts = tuple(
            (
                None
                if payload.get(field) is None
                else require_non_negative_exact_int(
                    payload.get(field),
                    type_message="OpenCL discovery account is invalid.",
                    range_message="OpenCL discovery account is invalid.",
                )
            )
            for field in ("effective_uid", "effective_gid")
        )
    except (ValidationError, ValueError) as exception:
        raise protocol_error("OpenCL discovery result is invalid.") from exception
    if state == OpenCLRuntimeState.READY and (
        texts[0] is not None or texts[1] not in STRONG_MATCH_BASES
    ):
        raise protocol_error("OpenCL discovery readiness has no strong identity authority.")
    if state != OpenCLRuntimeState.READY and not texts[0]:
        raise protocol_error("OpenCL discovery failure has no reason.")
    return OpenCLRuntimeTarget(
        device_id,
        vendor,
        state,
        texts[0],
        message,
        texts[1],
        texts[2],
        texts[3],
        accounts[0],
        accounts[1],
    )
