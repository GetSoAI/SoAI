"""SoAI - Motherboard information gathering [backend/hardware/info_motherboard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.platform import get_runtime_platform
from core.serialization.json_parsing import parse_json_value
from core.validation.strings import coerce_optional_trimmed_str
from hardware.windows_commands import build_windows_powershell_command

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

LOGGER_NAME = "SoAI.hardware.info_motherboard"
OPERATION_HARDWARE_INFO_MOTHERBOARD_WINDOWS_CIM = "hardware.info_motherboard.windows_cim"


__all__ = ("get_motherboard_info",)

WINDOWS_MOTHERBOARD_FAILURES: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
    StateError,
    ValidationError,
)


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
        info = read_windows_motherboard(executor).info
    return info


@dataclass(frozen=True, slots=True)
class WindowsMotherboardAcquisition:
    info: JSONDict
    state: Literal[
        "observed", "permission_denied", "runtime_unavailable", "query_failed", "invalid_response"
    ]
    diagnostic: SoAIError | None


def read_windows_motherboard(executor: CommandExecutorProtocol) -> WindowsMotherboardAcquisition:
    operation = "hardware.info_motherboard.windows_cim"
    try:
        result = executor.execute(
            build_windows_powershell_command(
                "Get-CimInstance -ClassName Win32_BaseBoard | Select-Object Manufacturer,Product,Version,SerialNumber | ConvertTo-Json -Compress"
            ),
            timeout=5,
            shell=False,
            use_sudo=False,
        )
        if result is None:
            raise ValidationError("Motherboard CIM response is missing.", operation=operation)
        if result.return_code != 0:
            raise StateError(
                "Motherboard CIM acquisition failed.",
                operation=operation,
                details={
                    "return_code": result.return_code,
                    "stderr": result.stderr,
                    "stdout": result.stdout,
                },
            )
        parsed: JSONValue = (
            parse_json_value(
                result.stdout, field="Win32_BaseBoard output", reject_duplicate_keys=True
            )
            if result.stdout.strip()
            else []
        )
        rows: list[JSONValue] = parsed if isinstance(parsed, list) else [parsed]
        field_map = {
            "Manufacturer": "manufacturer",
            "Product": "product_name",
            "Version": "version",
            "SerialNumber": "serialnumber",
        }
        entries: list[JSONDict] = []
        for row in rows:
            if not isinstance(row, dict) or any(
                row.get(field) is not None and not isinstance(row[field], str)
                for field in field_map
            ):
                raise ValidationError("Motherboard CIM response is invalid.", operation=operation)
            entry: JSONDict = {}
            for source, target in field_map.items():
                value = coerce_optional_trimmed_str(row.get(source))
                if value is not None:
                    entry[target] = value
            entries.append(entry)
        return WindowsMotherboardAcquisition(entries[0] if entries else {}, "observed", None)
    except WINDOWS_MOTHERBOARD_FAILURES as exception:
        state: Literal[
            "permission_denied", "runtime_unavailable", "query_failed", "invalid_response"
        ] = "query_failed"
        if isinstance(exception, PermissionError):
            state = "permission_denied"
        elif isinstance(exception, FileNotFoundError):
            state = "runtime_unavailable"
        elif isinstance(exception, ValidationError):
            state = "invalid_response"
        error = StateError(
            "Optional motherboard CIM information is unavailable.",
            operation=operation,
            cause=exception,
        )
        log_handled_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Optional motherboard information unavailable.",
            operation=OPERATION_HARDWARE_INFO_MOTHERBOARD_WINDOWS_CIM,
            level="warning",
        )
        return WindowsMotherboardAcquisition({}, state, error)
