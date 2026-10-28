"""SoAI - Intel XPU-SMI command helpers [backend/hardware/vendors/intel/commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError, ValidationError
from core.validation.strict_integer import is_strict_int
from hardware.vendors.command_probe import (
    JsonCommandProbeResult,
    JsonCommandProbeState,
    run_json_command_probe,
)
from hardware.vendors.intel.capability_parsing import (
    extract_intel_config_device,
    extract_intel_dump_devices,
)
from hardware.vendors.intel.runtime import resolve_xpu_smi_path

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONValue


__all__ = (
    "IntelReadDialect",
    "IntelReadError",
    "IntelReadState",
    "execute_intel_config_command",
    "execute_intel_config_json",
    "execute_intel_dump_json",
    "execute_intel_json_command",
    "resolve_intel_read_dialect",
)


class IntelReadState(StrEnum):
    TOOL_MISSING = "tool_missing"
    PERMISSION_DENIED = "permission_denied"
    TIMED_OUT = "timed_out"
    COMMAND_FAILED = "command_failed"
    UNSUPPORTED_PROTOCOL = "unsupported_protocol"
    UNSUPPORTED_DEVICE = "unsupported_device"
    SYSMAN_UNAVAILABLE = "sysman_unavailable"
    MALFORMED_RESPONSE = "malformed_response"


class IntelReadError(StateError):
    @property
    def state(self) -> IntelReadState:
        value = (self.details or {}).get("intel_read_state")
        if not isinstance(value, str):
            raise ValidationError("Intel read failure state is unavailable.")
        return IntelReadState(value)


@dataclass(frozen=True, slots=True)
class IntelReadDialect:
    executable: str
    protocol: Literal["legacy", "metrics"]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.executable, str)
            or not self.executable
            or "\0" in self.executable
            or self.protocol not in ("legacy", "metrics")
        ):
            raise ValidationError("Intel read dialect authority is invalid.")


def _read_failure(
    result: JsonCommandProbeResult | None = None,
    *,
    state: IntelReadState | None = None,
) -> IntelReadError:
    if result is not None and state is None:
        state = {
            JsonCommandProbeState.TOOL_MISSING: IntelReadState.TOOL_MISSING,
            JsonCommandProbeState.PERMISSION_DENIED: IntelReadState.PERMISSION_DENIED,
            JsonCommandProbeState.TIMED_OUT: IntelReadState.TIMED_OUT,
            JsonCommandProbeState.MALFORMED: IntelReadState.MALFORMED_RESPONSE,
        }.get(result.state, IntelReadState.COMMAND_FAILED)
        text = (f"{result.stdout}\n{result.stderr}").strip()
        if result.return_code != 0 and text == "Sysman driver initialization failed.":
            state = IntelReadState.SYSMAN_UNAVAILABLE
        elif result.return_code == 0 and "Usage: xpu-smi " in text:
            state = IntelReadState.UNSUPPORTED_PROTOCOL
    if state is None:
        raise ValidationError("Intel read failure requires its acquisition state.")
    return IntelReadError(
        "Intel read-only acquisition is unavailable.",
        operation="hardware_intel.command_read",
        details={
            **(result.private_details if result is not None else {}),
            "intel_read_state": state.value,
        },
        cause=result.failure if result is not None else None,
    )


def resolve_intel_read_dialect(executor: CommandExecutorProtocol) -> IntelReadDialect:
    executable = resolve_xpu_smi_path()
    result = run_json_command_probe(
        executor, [executable, "dump", "--help"], timeout=5, use_sudo=False
    )
    if result.return_code != 0:
        raise _read_failure(result)
    help_text = result.stdout
    if result.state != JsonCommandProbeState.MALFORMED or not help_text.startswith(
        "Dump device statistics data\n"
    ):
        raise _read_failure(result, state=IntelReadState.UNSUPPORTED_PROTOCOL)
    json_option = "-j,--json" in help_text
    dump_usage = "Usage: xpu-smi dump [Options]" in help_text.splitlines()
    new_options = (
        "--device,--id" in help_text,
        "--metrics,--select" in help_text,
        "--number,--count" in help_text,
    )
    metrics_selector_supported = "-1 = all" in help_text and "ALL" in help_text.split()
    if (
        dump_usage
        and json_option
        and all(new_options)
        and "-d,--device" not in help_text
        and metrics_selector_supported
    ):
        return IntelReadDialect(executable, "metrics")
    if dump_usage and json_option and "-d,--device" in help_text and not any(new_options):
        return IntelReadDialect(executable, "legacy")
    raise _read_failure(result, state=IntelReadState.UNSUPPORTED_PROTOCOL)


def execute_intel_json_command(
    executor: CommandExecutorProtocol,
    command: list[str],
    *,
    timeout: int,
    use_sudo: bool,
) -> JSONValue:
    result = run_json_command_probe(executor, command, timeout=timeout, use_sudo=use_sudo)
    if result.state != JsonCommandProbeState.OBSERVED or result.payload is None:
        raise _read_failure(result)
    return result.payload


def execute_intel_config_json(
    executor: CommandExecutorProtocol,
    vendor_id: int,
    *,
    dialect: IntelReadDialect | None = None,
) -> JSONValue:
    if not is_strict_int(vendor_id) or vendor_id < 0:
        raise StateError("Intel configuration requires a valid device locator.")
    authority = dialect if dialect is not None else resolve_intel_read_dialect(executor)
    payload = execute_intel_json_command(
        executor,
        [authority.executable, "config", "-d", str(vendor_id), "-j"],
        timeout=5,
        use_sudo=False,
    )
    if authority.protocol != "legacy":
        raise _read_failure(state=IntelReadState.UNSUPPORTED_PROTOCOL)
    device = extract_intel_config_device(payload)
    if not device:
        raise _read_failure(state=IntelReadState.UNSUPPORTED_DEVICE)
    if device.get("device_id") != vendor_id:
        raise _read_failure(state=IntelReadState.MALFORMED_RESPONSE)
    return payload


def execute_intel_dump_json(
    executor: CommandExecutorProtocol,
    vendor_id: int | None = None,
    *,
    dialect: IntelReadDialect | None = None,
) -> JSONValue:
    if vendor_id is not None and (not is_strict_int(vendor_id) or vendor_id < 0):
        raise StateError("Intel inventory requires a valid device locator.")
    authority = dialect if dialect is not None else resolve_intel_read_dialect(executor)
    command = [authority.executable, "dump"]
    if authority.protocol == "metrics":
        command.extend(["--device", str(vendor_id if vendor_id is not None else -1)])
        command.extend(["--metrics", "ALL", "--number", "1"])
    elif vendor_id is not None:
        command.extend(["-d", str(vendor_id)])
    command.append("-j")
    payload = execute_intel_json_command(executor, command, timeout=10, use_sudo=False)
    if authority.protocol != "legacy":
        raise _read_failure(state=IntelReadState.UNSUPPORTED_PROTOCOL)
    devices = extract_intel_dump_devices(payload)
    if vendor_id is not None and not devices:
        raise _read_failure(state=IntelReadState.UNSUPPORTED_DEVICE)
    if vendor_id is not None and any(
        device.get("device_id") is not None and device.get("device_id") != vendor_id
        for device in devices
    ):
        raise _read_failure(state=IntelReadState.MALFORMED_RESPONSE)
    return payload


def execute_intel_config_command(
    executor: CommandExecutorProtocol,
    vendor_id: int,
    args: tuple[str, ...],
    *,
    use_sudo: bool,
) -> None:
    command = [resolve_xpu_smi_path(), "config", "-d", str(vendor_id), *args]
    result = executor.execute(command, timeout=5, shell=False, use_sudo=use_sudo)
    if result.return_code != 0:
        raise StateError(result.stderr or "xpu-smi config command failed")
