"""SoAI - Bounded physically selected radeontop observations [backend/hardware/vendors/amd/radeontop_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
from shutil import which

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import open_text
from core.hardware.gpu_identity_normalization import observed_pci_bdf_components
from core.system.protocols import CommandExecutorProtocol
from core.types.json import JSONDict
from core.validation.numbers import coerce_float_from_json
from hardware.gpu_inventory.drm_physical_observations import parse_drm_uevent

__all__ = ("read_radeontop_telemetry",)


def _selected_bus(directory: str, pci_bdf: str) -> int:
    requested = observed_pci_bdf_components(pci_bdf)
    if requested is None or requested[0] is None or requested[3] is None:
        raise ValidationError("Radeontop requires a complete physical PCI identity.")
    candidates: set[str] = set()
    for name in os.listdir(directory):
        if re.fullmatch(r"card[0-9]+", name) is None:
            continue
        device = os.path.join(directory, name, "device")
        with open_text(os.path.join(device, "uevent"), encoding="utf-8") as handle:
            fields = parse_drm_uevent(handle.read(4096))
        if fields.get("PCI_ID", "").split(":")[0].casefold() != "1002":
            continue
        address = observed_pci_bdf_components(fields.get("PCI_SLOT_NAME", ""))
        if address is None or address[0] is None or address[3] is None:
            raise ValidationError("Radeontop cannot disambiguate the actual AMD PCI roster.")
        if address[1] == requested[1]:
            candidates.add(os.path.realpath(device))
            if address != requested or fields.get("DRIVER") != "radeon":
                raise StateError("Radeontop bus selector has competing physical authority.")
    if len(candidates) != 1:
        raise StateError("Radeontop bus selector has no unique physical device.")
    return requested[1]


def read_radeontop_telemetry(
    directory: str, pci_bdf: str, executor: CommandExecutorProtocol
) -> JSONDict:
    executable = which("radeontop")
    if executable is None:
        return {}
    bus = _selected_bus(directory, pci_bdf)
    result = executor.execute(
        [executable, "-b", f"{bus:02x}", "-d", "-", "-l", "1"],
        timeout=5,
        shell=False,
        use_sudo=False,
    )
    if result.return_code != 0:
        raise StateError(
            "Radeontop sensor query failed.", details={"native_status": result.return_code}
        )
    if len(result.stdout) > 65536:
        raise ValidationError("Radeontop observation exceeds its bounded input size.")
    rows = [row for row in result.stdout.splitlines() if re.match(r"[0-9]+\.[0-9]+: bus ", row)]
    if len(rows) != 1 or _selected_bus(directory, pci_bdf) != bus:
        raise ValidationError("Radeontop physical sample is unavailable or changed.")
    locator = re.search(r": bus ([0-9a-fA-F]+),", rows[0])
    if locator is None or int(locator[1], 16) != bus:
        raise ValidationError("Radeontop sample contradicts its selected physical bus.")
    metrics: JSONDict = {}
    for expression, field, factor, percentage in (
        (r", gpu ([^%, ]+)%", "core_utilization_percent", 1.0, True),
        (r", sclk [^,]*? ([^, ]+)ghz", "core_clock_mhz", 1000.0, False),
        (r", mclk [^,]*? ([^, ]+)ghz", "mem_clock_mhz", 1000.0, False),
    ):
        match = re.search(expression, rows[0])
        value = (
            coerce_float_from_json(match[1], default=None, allow_nonfinite=False) if match else None
        )
        if value is not None and value >= 0 and (not percentage or value <= 100):
            metrics[field] = value * factor
    return metrics
