"""SoAI - Windows-visible network adapter inventory query [backend/hardware/windows_network_adapters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.serialization.json_parsing import parse_json_str_list
from hardware.probe_failure_logging import execute_hardware_probe_command
from hardware.windows_commands import build_windows_powershell_command

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol

__all__ = (
    "WINDOWS_VISIBLE_ADAPTER_QUERY",
    "WINDOWS_VISIBLE_ADAPTER_QUERY_TIMEOUT_SECONDS",
    "query_windows_visible_adapter_names",
)

LOGGER_NAME = "SoAI.hardware.windows_network_adapters"
OPERATION = "hardware.windows_network_adapters.query"
WINDOWS_VISIBLE_ADAPTER_QUERY_TIMEOUT_SECONDS = 5
WINDOWS_VISIBLE_ADAPTER_QUERY = (
    "$ErrorActionPreference = 'Stop'; "
    "$names = @(Get-NetAdapter -Name '*' | ForEach-Object { [string]$_.Name }); "
    "$json = ConvertTo-Json -InputObject $names -Compress; "
    "[regex]::Replace($json, '[^\\x00-\\x7F]', "
    "{ param($match) '\\u{0:x4}' -f [int][char]$match.Value })"
)


def query_windows_visible_adapter_names(executor: CommandExecutorProtocol) -> list[str] | None:
    logger = get_logger(LOGGER_NAME)
    result = execute_hardware_probe_command(
        executor,
        build_windows_powershell_command(WINDOWS_VISIBLE_ADAPTER_QUERY),
        logger=logger,
        message="Failed to query Windows-visible network adapters.",
        operation=OPERATION,
        timeout=WINDOWS_VISIBLE_ADAPTER_QUERY_TIMEOUT_SECONDS,
    )
    if result is None:
        return None
    try:
        if result.return_code != 0:
            raise ValidationError(
                "Get-NetAdapter exited with a nonzero status.",
                details={"return_code": result.return_code, "stderr": result.stderr.strip()},
            )
        adapter_names = parse_json_str_list(result.stdout, field="Get-NetAdapter output")
        _require_unique_nonblank_adapter_names(adapter_names)
    except ValidationError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Windows-visible network adapter inventory is unavailable.",
            operation=OPERATION,
            level="trace",
        )
        return None
    return adapter_names


def _require_unique_nonblank_adapter_names(adapter_names: list[str]) -> None:
    seen_aliases: set[str] = set()
    for adapter_name in adapter_names:
        if not adapter_name.strip():
            raise ValidationError("Get-NetAdapter output contains a blank adapter name.")
        alias = adapter_name.casefold()
        if alias in seen_aliases:
            raise ValidationError(
                "Get-NetAdapter output contains duplicate adapter names.",
                details={"adapter_name": adapter_name},
            )
        seen_aliases.add(alias)
