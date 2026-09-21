"""SoAI - SoAIBench public-document validation [backend/hardware/soaibench/publication_document_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
import unicodedata

from core.errors.exceptions import ValidationError
from core.hardware.soaibench_score_fields import SOAIBENCH_MEASUREMENT_FIELDS
from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_json_dict_or_empty
from core.validation.integers import is_strict_int
from hardware.soaibench.publication_numeric_validation import (
    require_optional_public_number,
    require_public_integer,
    require_public_number,
    validate_public_benchmark_numbers,
    validate_public_certification_numbers,
    validate_public_pass_numbers,
    validate_public_temperature_threshold,
)
from hardware.soaibench.publication_workload_validation import (
    WORKLOAD_FIELDS,
    WORKLOAD_PHASE_FIELDS,
    validate_public_workload,
)

PASS_FIELDS = (
    "index",
    "warmup",
    "score_version",
    *SOAIBENCH_MEASUREMENT_FIELDS,
    "workload",
)
TELEMETRY_FIELDS = (
    "telemetry_available",
    "throttle_detected",
    "unavailable_sensors",
    "temperature_celsius",
    "max_temperature_celsius",
    "power_draw_watts",
    "avg_power_watts",
    "max_power_watts",
    "core_utilization_percent",
)
BENCHMARK_FIELDS = (
    "score_version",
    "profile",
    "benchmark_mode",
    "status",
    "started_at_ms",
    "completed_at_ms",
    *SOAIBENCH_MEASUREMENT_FIELDS,
    "score_variance_percent",
)
GPU_FIELDS = ("gpu_name", "gpu_model_key", "vendor", "driver_version", "kernel_driver")
RUNTIME_FIELDS = (
    "soai_version",
    "os",
    "os_release",
    "machine",
    "cpu_name",
    "system_ram_gb",
    "opencl_platform_name",
    "opencl_platform_vendor",
    "opencl_device_name",
    "opencl_device_vendor",
    "opencl_driver_version",
    "opencl_queue_api",
)
CERTIFICATION_FIELDS = (
    "mode",
    "warmup_pass_count",
    "measured_pass_count",
    "leaderboard_eligible",
    "leaderboard_rejection_reason",
    "score_variance_percent",
    "phase_variation_percent",
    "phase_drift_percent",
    "score_confidence",
)
SETTINGS_FIELDS = ("power_limit_watts", "fan_speed", "core_clock_mhz", "mem_clock_mhz")

__all__ = (
    "BENCHMARK_FIELDS",
    "CERTIFICATION_FIELDS",
    "PASS_FIELDS",
    "SETTINGS_FIELDS",
    "TELEMETRY_FIELDS",
    "WORKLOAD_FIELDS",
    "WORKLOAD_PHASE_FIELDS",
    "normalize_public_text",
    "validate_publication_document",
)


def normalize_public_text(
    value: JSONValue, *, required: bool, allow_empty: bool, maximum_bytes: int = 128
) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ValidationError("SoAIBench public text evidence is invalid.")
    normalized = unicodedata.normalize("NFC", value).strip()
    if (not normalized and not allow_empty) or len(normalized.encode("utf-8")) > maximum_bytes:
        raise ValidationError("SoAIBench public text evidence is invalid.")
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in normalized):
        raise ValidationError("SoAIBench public text evidence is invalid.")
    return normalized


def validate_publication_document(document: JSONDict) -> None:
    _exact_fields(
        document,
        (
            "submission_version",
            "presentation",
            "benchmark",
            "gpu",
            "runtime",
            "evidence",
        ),
        "SoAIBench publication document",
    )
    presentation = coerce_json_dict_or_empty(document.get("presentation"))
    benchmark = coerce_json_dict_or_empty(document.get("benchmark"))
    gpu = coerce_json_dict_or_empty(document.get("gpu"))
    runtime = coerce_json_dict_or_empty(document.get("runtime"))
    evidence = coerce_json_dict_or_empty(document.get("evidence"))
    certification = coerce_json_dict_or_empty(evidence.get("certification"))
    settings = coerce_json_dict_or_empty(evidence.get("gpu_settings"))
    _exact_fields(presentation, ("display_name",), "SoAIBench presentation")
    _exact_fields(benchmark, BENCHMARK_FIELDS, "SoAIBench benchmark")
    _exact_fields(gpu, GPU_FIELDS, "SoAIBench GPU")
    _exact_fields(runtime, RUNTIME_FIELDS, "SoAIBench runtime")
    _exact_fields(certification, CERTIFICATION_FIELDS, "SoAIBench certification")
    _exact_fields(
        evidence,
        (
            "measured_passes",
            "telemetry_summary",
            "certification",
            "gpu_settings",
            "temperature_limit_celsius",
            "warmup_active_seconds",
        ),
        "SoAIBench evidence",
    )
    if (
        document.get("submission_version") != "soaibench-submission-v1"
        or presentation.get("display_name") != "Anonymous"
        or benchmark.get("score_version") != "soaibench-v2"
    ):
        raise ValidationError("SoAIBench publication document version is invalid.")
    validate_public_benchmark_numbers(benchmark)
    validate_public_certification_numbers(certification)
    require_public_number(evidence.get("warmup_active_seconds"), minimum=120.0)
    _validate_gpu(gpu)
    _validate_runtime(runtime)
    _validate_telemetry(coerce_json_dict_or_empty(evidence.get("telemetry_summary")))
    passes = evidence.get("measured_passes")
    if not isinstance(passes, list) or len(passes) != 5:
        raise ValidationError("SoAIBench public measured-pass evidence is invalid.")
    telemetry_observations = [coerce_json_dict_or_empty(evidence.get("telemetry_summary"))]
    for index, entry in enumerate(passes, start=1):
        if not isinstance(entry, dict):
            raise ValidationError("SoAIBench public measured-pass evidence is invalid.")
        _exact_fields(entry, (*PASS_FIELDS, "telemetry"), "SoAIBench measured pass")
        if (
            not is_strict_int(entry.get("index"))
            or entry.get("index") != index
            or entry.get("warmup") is not False
            or entry.get("score_version") != "soaibench-v2"
        ):
            raise ValidationError("SoAIBench public measured-pass ordering is invalid.")
        validate_public_pass_numbers(entry)
        minimum_duration_ms = validate_public_workload(
            coerce_json_dict_or_empty(entry.get("workload"))
        )
        if require_public_integer(entry.get("duration_ms")) < minimum_duration_ms:
            raise ValidationError("SoAIBench measured-pass duration is inconsistent.")
        pass_telemetry = coerce_json_dict_or_empty(entry.get("telemetry"))
        _validate_telemetry(pass_telemetry)
        telemetry_observations.append(pass_telemetry)
    if set(settings) - set(SETTINGS_FIELDS):
        raise ValidationError("SoAIBench settings contain an unexpected field.")
    for field, maximum in (
        ("power_limit_watts", 1_000_000.0),
        ("fan_speed", 100.0),
        ("core_clock_mhz", 10_000_000.0),
        ("mem_clock_mhz", 10_000_000.0),
    ):
        require_optional_public_number(settings.get(field), minimum=0.0, maximum=maximum)
    require_optional_public_number(
        evidence.get("temperature_limit_celsius"), minimum=-273.15, maximum=1000.0
    )
    validate_public_temperature_threshold(
        evidence.get("temperature_limit_celsius"),
        telemetry_observations,
    )


def _validate_gpu(gpu: JSONDict) -> None:
    gpu_name = normalize_public_text(gpu.get("gpu_name"), required=False, allow_empty=True)
    model_key = normalize_public_text(gpu.get("gpu_model_key"), required=False, allow_empty=True)
    if not gpu_name and not model_key:
        raise ValidationError("SoAIBench public GPU identity is incomplete.")
    if model_key is not None and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", model_key) is None:
        raise ValidationError("SoAIBench public GPU model key is invalid.")
    for field in ("vendor", "driver_version", "kernel_driver"):
        normalize_public_text(gpu.get(field), required=False, allow_empty=True)


def _validate_runtime(runtime: JSONDict) -> None:
    for field in ("soai_version", "os", "opencl_device_name"):
        normalize_public_text(runtime.get(field), required=True, allow_empty=False)
    normalize_public_text(
        runtime.get("cpu_name"), required=True, allow_empty=False, maximum_bytes=512
    )
    for field in (
        "os_release",
        "machine",
        "opencl_platform_name",
        "opencl_platform_vendor",
        "opencl_device_vendor",
        "opencl_driver_version",
        "opencl_queue_api",
    ):
        normalize_public_text(runtime.get(field), required=False, allow_empty=False)
    require_public_number(
        runtime.get("system_ram_gb"),
        minimum=0.0,
        maximum=1_000_000.0,
        allow_zero=False,
    )


def _validate_telemetry(telemetry: JSONDict) -> None:
    _exact_fields(telemetry, TELEMETRY_FIELDS, "SoAIBench telemetry")
    if not isinstance(telemetry.get("telemetry_available"), bool):
        raise ValidationError("SoAIBench public telemetry availability is invalid.")
    throttle = telemetry.get("throttle_detected")
    if throttle is not None and not isinstance(throttle, bool):
        raise ValidationError("SoAIBench public throttle evidence is invalid.")
    unavailable = telemetry.get("unavailable_sensors")
    if not isinstance(unavailable, list) or unavailable != [
        sensor for sensor in ("temperature", "power") if sensor in unavailable
    ]:
        raise ValidationError("SoAIBench public sensor evidence is invalid.")
    temperature_values = (
        telemetry.get("temperature_celsius"),
        telemetry.get("max_temperature_celsius"),
    )
    power_values = (
        telemetry.get("power_draw_watts"),
        telemetry.get("avg_power_watts"),
        telemetry.get("max_power_watts"),
    )
    expected_unavailable: list[str] = []
    if all(value is None for value in temperature_values):
        expected_unavailable.append("temperature")
    if all(value is None for value in power_values):
        expected_unavailable.append("power")
    expected_available = (
        any(value is not None for value in (*temperature_values, *power_values))
        or telemetry.get("core_utilization_percent") is not None
    )
    if (
        unavailable != expected_unavailable
        or telemetry.get("telemetry_available") is not expected_available
    ):
        raise ValidationError("SoAIBench public sensor availability is inconsistent.")
    for field in ("temperature_celsius", "max_temperature_celsius"):
        require_optional_public_number(telemetry.get(field), minimum=-273.15, maximum=1000.0)
    for field in ("power_draw_watts", "avg_power_watts", "max_power_watts"):
        require_optional_public_number(telemetry.get(field), minimum=0.0, maximum=1_000_000.0)
    require_optional_public_number(
        telemetry.get("core_utilization_percent"), minimum=0.0, maximum=100.0
    )


def _exact_fields(payload: JSONDict, fields: tuple[str, ...], label: str) -> None:
    if set(payload) != set(fields):
        raise ValidationError(f"{label} fields are invalid.")
