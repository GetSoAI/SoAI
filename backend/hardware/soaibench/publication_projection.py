"""SoAI - Anonymous SoAIBench public projection [backend/hardware/soaibench/publication_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.hardware.gpu_identity_normalization import is_specific_gpu_name, normalize_identity_name
from core.hardware.soaibench_telemetry import project_public_telemetry
from core.serialization.json import serialize_json_compact_stable
from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_json_dict_or_empty
from hardware.soaibench.publication_document_validation import (
    BENCHMARK_FIELDS,
    CERTIFICATION_FIELDS,
    PASS_FIELDS,
    SETTINGS_FIELDS,
    WORKLOAD_FIELDS,
    normalize_public_text,
    validate_publication_document,
)

__all__ = ("build_publication_document", "resolve_public_gpu_name")


def build_publication_document(
    run: JSONDict,
    measured_passes: list[JSONDict],
) -> str:
    environment = coerce_json_dict_or_empty(run.get("environment"))
    opencl = coerce_json_dict_or_empty(environment.get("opencl"))
    document: JSONDict = {
        "submission_version": "soaibench-submission-v1",
        "presentation": {"display_name": "Anonymous"},
        "benchmark": {field: run.get(field) for field in BENCHMARK_FIELDS},
        "gpu": _gpu(run, environment),
        "runtime": _runtime(environment, opencl),
        "evidence": {
            "measured_passes": [_project_pass(entry) for entry in measured_passes],
            "telemetry_summary": project_public_telemetry(
                coerce_json_dict_or_empty(run.get("summary"))
            ),
            "certification": _certification(run),
            "gpu_settings": _gpu_settings(run),
            "temperature_limit_celsius": coerce_json_dict_or_empty(run.get("summary")).get(
                "temperature_limit_celsius"
            ),
            "warmup_active_seconds": coerce_json_dict_or_empty(run.get("summary")).get(
                "warmup_active_seconds"
            ),
        },
    }
    validate_publication_document(document)
    return serialize_json_compact_stable(document, ensure_ascii=False)


def _gpu(run: JSONDict, environment: JSONDict) -> JSONDict:
    identity = coerce_json_dict_or_empty(environment.get("gpu_identity"))
    opencl = coerce_json_dict_or_empty(environment.get("opencl"))
    gpu_name = resolve_public_gpu_name(run, opencl)
    vendor = run.get("vendor")
    if vendor is None or (
        isinstance(vendor, str) and normalize_identity_name(vendor) in {"", "unknown"}
    ):
        vendor = opencl.get("device_vendor") or opencl.get("platform_vendor")
    return {
        "gpu_name": normalize_public_text(gpu_name, required=False, allow_empty=True),
        "gpu_model_key": normalize_public_text(
            run.get("gpu_model_key"), required=False, allow_empty=True
        ),
        "vendor": normalize_public_text(vendor, required=False, allow_empty=True),
        "driver_version": normalize_public_text(
            _public_driver_version(run, environment), required=False, allow_empty=True
        ),
        "kernel_driver": normalize_public_text(
            identity.get("kernel_driver"), required=False, allow_empty=True
        ),
    }


def _public_driver_version(run: JSONDict, environment: JSONDict) -> JSONValue:
    value = run.get("driver_version")
    vendor = run.get("vendor")
    if (
        not isinstance(value, str)
        or not isinstance(vendor, str)
        or normalize_identity_name(vendor) != "amd"
        or environment.get("os") != "Linux"
    ):
        return value
    match = re.match(r"Linux\s*version\s*([0-9][A-Za-z0-9.+~_-]*)\s*\(", value)
    if match is not None and match.group(1) == environment.get("os_release"):
        return match.group(1)
    return value


def resolve_public_gpu_name(run: JSONDict, opencl: JSONDict) -> JSONValue:
    gpu_name = run.get("gpu_name")
    if gpu_name is None:
        return opencl.get("device_name")
    if isinstance(gpu_name, str) and not is_specific_gpu_name(gpu_name):
        return opencl.get("device_name")
    return gpu_name


def _runtime(environment: JSONDict, opencl: JSONDict) -> JSONDict:
    values = {
        "soai_version": environment.get("soai_version"),
        "os": environment.get("os"),
        "os_release": environment.get("os_release"),
        "machine": environment.get("machine"),
        "cpu_name": environment.get("cpu_name"),
        "system_ram_gb": environment.get("system_ram_gb"),
        "opencl_platform_name": opencl.get("platform_name"),
        "opencl_platform_vendor": opencl.get("platform_vendor"),
        "opencl_device_name": opencl.get("device_name"),
        "opencl_device_vendor": opencl.get("device_vendor"),
        "opencl_driver_version": opencl.get("driver_version"),
        "opencl_queue_api": opencl.get("queue_api"),
    }
    required_text = {"soai_version", "os", "cpu_name", "opencl_device_name"}
    return {
        field: (
            value
            if field == "system_ram_gb"
            else normalize_public_text(
                (
                    None
                    if field not in required_text and isinstance(value, str) and not value.strip()
                    else value
                ),
                required=field in required_text,
                allow_empty=False,
                maximum_bytes=512 if field == "cpu_name" else 128,
            )
        )
        for field, value in values.items()
    }


def _project_pass(measured: JSONDict) -> JSONDict:
    projected = {field: measured.get(field) for field in PASS_FIELDS}
    workload = coerce_json_dict_or_empty(measured.get("workload"))
    workload_evidence = coerce_json_dict_or_empty(workload.get("workload_evidence"))
    projected["workload"] = {name: workload_evidence.get(name) for name in WORKLOAD_FIELDS}
    projected["telemetry"] = project_public_telemetry(
        coerce_json_dict_or_empty(measured.get("telemetry"))
    )
    return projected


def _certification(run: JSONDict) -> JSONDict:
    certification = coerce_json_dict_or_empty(run.get("certification"))
    return {field: certification.get(field) for field in CERTIFICATION_FIELDS}


def _gpu_settings(run: JSONDict) -> JSONDict:
    settings = coerce_json_dict_or_empty(run.get("settings_snapshot"))
    return {field: value for field in SETTINGS_FIELDS if (value := settings.get(field)) is not None}
