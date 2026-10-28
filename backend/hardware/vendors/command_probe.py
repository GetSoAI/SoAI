"""SoAI - Shared vendor JSON command probes [backend/hardware/vendors/command_probe.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import SoAITimeoutError, StateError, ValidationError
from core.serialization.json_parsing import MAX_JSON_NESTING_DEPTH, parse_json_value
from core.validation.strict_integer import is_strict_int

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue


__all__ = (
    "JsonCommandProbeState",
    "JsonCommandProbeResult",
    "run_json_command_probe",
    "require_json_command_payload",
)


class JsonCommandProbeState(StrEnum):
    OBSERVED = "observed"
    COMMAND_FAILED = "command_failed"
    TOOL_MISSING = "tool_missing"
    PERMISSION_DENIED = "permission_denied"
    TIMED_OUT = "timed_out"
    MALFORMED = "malformed"


@dataclass(frozen=True, slots=True)
class JsonCommandProbeResult:
    return_code: int | None
    stderr: str
    payload: JSONValue | None
    state: JsonCommandProbeState
    stdout: str
    diagnostics: tuple[str, ...]
    failure: Exception | None

    @property
    def private_details(self) -> JSONDict:
        return {
            "probe_state": self.state.value,
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "diagnostics": list(self.diagnostics),
        }


_AMD_PERMISSION_BANNER = (
    r"Permission needed to access required GPU device node\(s\):\n"
    r"(?=  • /dev/(?:kfd|dri/render[D]\*))"
    r"(?:  • /dev/kfd: Permission denied\n"
    r"    - Required group:\n"
    r"      - User: [a-zA-Z0-9_-]+ \(UID=\d+\) \| Group: [a-zA-Z0-9_-]+ \(GID=\d+\)\n)?"
    r"(?:  • /dev/dri/render[D]\*: [1-9]\d* device\(s\) denied\n"
    r"    - Required group:\n"
    r"      - User: [a-zA-Z0-9_-]+ \(UID=\d+\) \| Group: [a-zA-Z0-9_-]+ \(GID=\d+\)\n)?"
    r"\nTo resolve this issue, try the following:\n"
    r"  • Add your user to the required group\(s\):\n"
    r'      sudo usermod -aG [a-zA-Z0-9_-]+ "\$USER"\n'
    r"  • Log out and log back in for the group changes to take effect\n"
    r"  • Alternatively, run this command with sudo/admin privileges\n\n"
)
_AMD_LINK_WIDTH_DIAGNOSTIC = "Failed to open file: /sys/class/drm//device/max_link_width"


def _amd_json_framing(stdout: str) -> tuple[str, tuple[str, ...]]:
    normalized = stdout.replace("\r\n", "\n")
    diagnostics: list[str] = []
    banner = re.match(_AMD_PERMISSION_BANNER, normalized)
    if banner is not None:
        diagnostics.append(banner[0])
        normalized = normalized[banner.end() :]
    stripped = normalized.rstrip()
    if stripped.endswith(f"\n{_AMD_LINK_WIDTH_DIAGNOSTIC}"):
        diagnostics.append(normalized[len(stripped) - len(_AMD_LINK_WIDTH_DIAGNOSTIC) :])
        normalized = stripped[: -len(_AMD_LINK_WIDTH_DIAGNOSTIC)]
    return normalized, tuple(diagnostics)


def run_json_command_probe(
    executor: CommandExecutorProtocol,
    command: Sequence[str],
    *,
    timeout: int,
    use_sudo: bool,
    json_field: str = "json",
    framing: Literal["strict", "amd_smi"] = "strict",
) -> JsonCommandProbeResult:
    if framing not in ("strict", "amd_smi"):
        raise ValidationError("The vendor JSON framing policy is invalid.")
    try:
        result = executor.execute(list(command), timeout=timeout, shell=False, use_sudo=use_sudo)
    except (OSError, SoAITimeoutError) as exception:
        state = JsonCommandProbeState.COMMAND_FAILED
        if isinstance(exception, TimeoutError | SoAITimeoutError):
            state = JsonCommandProbeState.TIMED_OUT
        elif isinstance(exception, FileNotFoundError):
            state = JsonCommandProbeState.TOOL_MISSING
        elif isinstance(exception, PermissionError):
            state = JsonCommandProbeState.PERMISSION_DENIED
        return JsonCommandProbeResult(None, "", None, state, "", (), exception)
    if (
        not is_strict_int(result.return_code)
        or not isinstance(result.stdout, str)
        or not isinstance(result.stderr, str)
    ):
        raise ValidationError("The vendor command response violates its declared contract.")
    if result.return_code != 0:
        state = (
            JsonCommandProbeState.TOOL_MISSING
            if result.return_code == 127
            else JsonCommandProbeState.COMMAND_FAILED
        )
        return JsonCommandProbeResult(
            result.return_code, result.stderr, None, state, result.stdout, (), None
        )
    json_text, diagnostics = (
        _amd_json_framing(result.stdout) if framing == "amd_smi" else (result.stdout, ())
    )
    try:
        payload = parse_json_value(
            json_text,
            field=json_field,
            max_depth=MAX_JSON_NESTING_DEPTH,
            reject_duplicate_keys=True,
        )
        if payload is None or (framing == "amd_smi" and not isinstance(payload, dict | list)):
            raise ValidationError("The vendor command did not return its expected JSON data.")
    except ValidationError as exception:
        return JsonCommandProbeResult(
            result.return_code,
            result.stderr,
            None,
            JsonCommandProbeState.MALFORMED,
            result.stdout,
            diagnostics,
            exception,
        )
    return JsonCommandProbeResult(
        result.return_code,
        result.stderr,
        payload,
        JsonCommandProbeState.OBSERVED,
        result.stdout,
        diagnostics,
        None,
    )


def require_json_command_payload(
    executor: CommandExecutorProtocol,
    command: Sequence[str],
    *,
    timeout: int,
    use_sudo: bool,
    failure_message: str,
    json_field: str = "json",
    framing: Literal["strict", "amd_smi"] = "strict",
) -> JSONValue:
    result = run_json_command_probe(
        executor,
        command,
        timeout=timeout,
        use_sudo=use_sudo,
        json_field=json_field,
        framing=framing,
    )
    if result.state != JsonCommandProbeState.OBSERVED or result.payload is None:
        raise StateError(
            failure_message,
            details=result.private_details,
            cause=result.failure,
        )
    return result.payload
