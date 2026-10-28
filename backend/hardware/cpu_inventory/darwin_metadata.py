"""SoAI - Darwin CPU identity and nominal metadata acquisition [backend/hardware/cpu_inventory/darwin_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from core.validation.numbers import coerce_float_from_json, coerce_int_from_json

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "SYSCTL_KEYS",
    "read_darwin_cpu_metadata",
)

SYSCTL_KEYS = (
    "machdep.cpu.brand_string",
    "hw.model",
    "hw.packages",
    "hw.cpufrequency",
    "hw.cpufrequency_min",
    "hw.cpufrequency_max",
    "hw.l3cachesize",
)


def read_darwin_cpu_metadata(executor: CommandExecutorProtocol) -> JSONDict:
    sysctl_path = shutil.which("sysctl")
    if not sysctl_path:
        return {"metadata_status": "unavailable"}
    result = executor.execute([sysctl_path, *SYSCTL_KEYS], timeout=3, shell=False, use_sudo=False)
    fields: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() in SYSCTL_KEYS:
            fields[key.strip()] = value.strip()
    package_count = coerce_int_from_json(fields.get("hw.packages"))
    valid_package_count = package_count if package_count is not None and package_count > 0 else None
    validated_fields: set[str] = {"hw.packages"} if valid_package_count is not None else set()
    metadata: JSONDict = {
        "metadata_status": "unavailable",
        "package_count": valid_package_count,
        "current_freq_mhz": None,
    }
    brand = fields.get("machdep.cpu.brand_string")
    if brand:
        metadata["name"] = brand
        validated_fields.add("machdep.cpu.brand_string")
    for native_key, output_key, divisor in (
        ("hw.cpufrequency", "nominal_freq_mhz", 1000000),
        ("hw.cpufrequency_min", "min_freq_mhz", 1000000),
        ("hw.cpufrequency_max", "max_freq_mhz", 1000000),
        ("hw.l3cachesize", "l3_cache_kb", 1024),
    ):
        native_value = coerce_float_from_json(fields.get(native_key), default=None)
        metadata[output_key] = (
            native_value / divisor if native_value is not None and native_value >= 0 else None
        )
        if metadata[output_key] is not None:
            validated_fields.add(native_key)
    if fields.get("hw.model"):
        validated_fields.add("hw.model")
    useful_fields = validated_fields - {"hw.model"}
    if useful_fields:
        metadata["metadata_status"] = (
            "available"
            if result.return_code == 0 and validated_fields == set(SYSCTL_KEYS)
            else "partial"
        )
    return metadata
