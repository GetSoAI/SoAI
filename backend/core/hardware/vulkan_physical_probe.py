"""SoAI - Vulkan physical device probe in an owned child process [backend/core/hardware/vulkan_physical_probe.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys

from core.errors.exceptions import ValidationError
from core.hardware.vulkan_physical_acquisition import (
    acquire_vulkan_physical_devices,
    load_vulkan_library,
)
from core.hardware.windows_adapter_address import load_windows_adapter_library
from core.meta.paths import get_backend_root
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.system.commands import run_argv_capture
from core.types.json import JSONDict, is_json_dict

__all__ = (
    "main",
    "run_vulkan_physical_probe",
)

PROBE_MODULE = "core.hardware.vulkan_physical_probe"


def run_vulkan_physical_probe(timeout_seconds: int) -> tuple[JSONDict, ...] | None:
    executable = sys.executable.strip()
    if not executable:
        return None
    result = run_argv_capture(
        [executable, "-m", PROBE_MODULE],
        timeout=timeout_seconds,
        cwd=get_backend_root(),
    )
    if result.timed_out or result.return_code != 0:
        return None
    try:
        payload = parse_json_dict(result.stdout, field=PROBE_MODULE, reject_duplicate_keys=True)
    except ValidationError:
        return None
    devices = payload.get("devices")
    if not isinstance(devices, list) or not all(is_json_dict(device) for device in devices):
        return None
    return tuple(device for device in devices if is_json_dict(device))


def main() -> None:
    devices = acquire_vulkan_physical_devices(load_vulkan_library(), load_windows_adapter_library())
    sys.stdout.write(serialize_json_compact_stable_strict({"devices": list(devices)}))


if __name__ == "__main__":
    main()
