"""SoAI - Shared vendor JSON command probes [backend/hardware/vendors/command_probe.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.serialization.json_parsing import parse_json_value

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONValue

__all__ = (
    "JsonCommandProbeResult",
    "require_json_command_payload",
    "run_json_command_probe",
)


@dataclass(frozen=True, slots=True)
class JsonCommandProbeResult:
    return_code: int
    stderr: str
    payload: JSONValue | None


def run_json_command_probe(
    executor: CommandExecutorProtocol,
    command: Sequence[str],
    *,
    timeout: int,
    use_sudo: bool,
    json_field: str = "json",
) -> JsonCommandProbeResult:
    result = executor.execute(list(command), timeout=timeout, shell=False, use_sudo=use_sudo)
    payload = (
        parse_json_value(result.stdout, field=json_field)
        if result.return_code == 0 and result.stdout
        else None
    )
    return JsonCommandProbeResult(
        return_code=result.return_code,
        stderr=result.stderr,
        payload=payload,
    )


def require_json_command_payload(
    executor: CommandExecutorProtocol,
    command: Sequence[str],
    *,
    timeout: int,
    use_sudo: bool,
    failure_message: str,
    json_field: str = "json",
) -> JSONValue:
    result = run_json_command_probe(
        executor,
        command,
        timeout=timeout,
        use_sudo=use_sudo,
        json_field=json_field,
    )
    if result.return_code != 0 or result.payload is None:
        raise StateError(result.stderr or failure_message)
    return result.payload
