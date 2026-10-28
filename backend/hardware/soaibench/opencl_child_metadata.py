"""SoAI - OpenCL child device and capability evidence validation [backend/hardware/soaibench/opencl_child_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict, JSONValue
from core.validation.strict_integer import is_strict_int
from hardware.soaibench.opencl_child_protocol import protocol_error

__all__ = (
    "bounded_child_nonempty_text",
    "bounded_child_optional_text",
    "validate_child_device_metadata",
    "validate_child_capability_evidence",
)


def validate_child_device_metadata(payload: JSONDict) -> None:
    if payload.get("queue_api") not in {
        "clCreateCommandQueue",
        "clCreateCommandQueueWithProperties",
    }:
        raise protocol_error("SoAI Bench child queue API is invalid.")
    for field in ("match_basis", "opencl_device_name"):
        bounded_child_nonempty_text(payload.get(field), field)
    for field in (
        "opencl_platform_name",
        "opencl_platform_vendor",
        "opencl_device_vendor",
        "opencl_driver_version",
    ):
        bounded_child_optional_text(payload.get(field), field)


def bounded_child_optional_text(value: JSONValue, field: str) -> str:
    if not isinstance(value, str) or len(value.encode("utf-8")) > 4096:
        raise protocol_error(f"SoAI Bench child {field} is invalid.")
    return value


def bounded_child_nonempty_text(value: JSONValue, field: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 4096:
        raise protocol_error(f"SoAI Bench child {field} is invalid.")
    return value


def validate_child_capability_evidence(value: JSONValue) -> None:
    fields = {
        "device_type",
        "device_profile",
        "device_available",
        "compiler_available",
        "execution_capabilities",
        "compiler",
        "custom_discovery_warning",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise protocol_error("SoAI Bench child capability fields are invalid.")
    device_type = value["device_type"]
    if not is_strict_int(device_type) or not 0 < device_type < 2**64:
        raise protocol_error("SoAI Bench child device type is invalid.")
    execution = value["execution_capabilities"]
    if execution is not None and (not is_strict_int(execution) or not 0 <= execution < 2**64):
        raise protocol_error("SoAI Bench child execution capabilities are invalid.")
    for field in ("device_available", "compiler_available"):
        if value[field] is not None and not isinstance(value[field], bool):
            raise protocol_error("SoAI Bench child availability evidence is invalid.")
    if value["device_profile"] is not None:
        bounded_child_optional_text(value["device_profile"], "device_profile")
    warning = value["custom_discovery_warning"]
    if warning is not None and (
        not isinstance(warning, str) or len(warning.encode("utf-8")) > 8192
    ):
        raise protocol_error("SoAI Bench child Custom discovery warning is invalid.")
    compiler = value["compiler"]
    if not isinstance(compiler, dict) or set(compiler) != {
        "radeonsi_force_use_fma32",
        "mesa_shader_cache_disable",
    }:
        raise protocol_error("SoAI Bench child compiler evidence is invalid.")
    for field in ("radeonsi_force_use_fma32", "mesa_shader_cache_disable"):
        if compiler[field] is not None:
            bounded_child_optional_text(compiler[field], field)
