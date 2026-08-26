"""SoAI - Motherboard information gathering [backend/hardware/info_motherboard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.runtime.platform import get_runtime_platform

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("get_motherboard_info",)


def get_motherboard_info(executor: CommandExecutorProtocol) -> JSONDict:
    info: JSONDict = {}
    runtime_platform = get_runtime_platform()
    if runtime_platform.is_linux:
        result = executor.execute(
            ["dmidecode", "-t", "baseboard"],
            timeout=5,
            shell=False,
            use_sudo=True,
        )
        if result.stdout:
            key_map = {
                "manufacturer": "manufacturer",
                "product name": "productname",
                "version": "version",
                "serial number": "serialnumber",
            }
            for line in result.stdout.splitlines():
                if ":" in line:
                    key, value = (sentence.strip() for sentence in line.split(":", 1))
                    norm_key = key.lower()
                    if norm_key in key_map and value:
                        info[key_map[norm_key]] = value
    elif runtime_platform.is_windows:
        for item in ["manufacturer", "product", "version", "serialnumber"]:
            result = executor.execute(
                ["wmic", "baseboard", "get", item],
                timeout=5,
                shell=False,
                use_sudo=False,
            )
            lines = result.stdout.strip().splitlines()
            if result.stdout and len(lines) > 1:
                info[f"{item}_name" if item == "product" else item] = lines[1].strip()
    return info
