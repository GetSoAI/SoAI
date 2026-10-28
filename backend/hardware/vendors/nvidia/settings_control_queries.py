"""SoAI - Typed NVIDIA settings query and native attribute grammar [backend/hardware/vendors/nvidia/settings_control_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from core.concurrency.deadlines import MonotonicDeadline
from core.errors.exceptions import StateError, ValidationError
from core.system.commands import require_command_result
from core.validation.strict_integer import is_strict_int
from hardware.gpu_inventory.executable_resolution import GpuExecutableState
from hardware.vendors.nvidia.smi_display_environment import (
    NvidiaDisplayQuery,
    display_process_environment,
)

__all__ = (
    "NvidiaSettingsSession",
    "NvidiaSettingsAttribute",
    "NvidiaSettingsFan",
    "NvidiaSettingsPerformanceMode",
    "query_settings_output",
    "parse_settings_attribute",
    "query_settings_fans",
    "query_settings_performance_modes",
    "invoke_settings_attribute",
)


@dataclass(frozen=True, slots=True)
class NvidiaSettingsSession:
    query: NvidiaDisplayQuery
    display: str
    xauthority: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.query, NvidiaDisplayQuery):
            raise ValidationError("NVIDIA settings session requires actual query resources.")
        if not isinstance(self.display, str) or not re.fullmatch(r":\d+(?:\.\d+)?", self.display):
            raise ValidationError("NVIDIA settings display is invalid.")
        if self.xauthority is not None and (
            not isinstance(self.xauthority, str) or not self.xauthority
        ):
            raise ValidationError("NVIDIA settings display authorization is invalid.")


@dataclass(frozen=True, slots=True)
class NvidiaSettingsAttribute:
    value: int
    minimum: int | None
    maximum: int | None


@dataclass(frozen=True, slots=True)
class NvidiaSettingsFan:
    native_fan_id: int
    attribute: NvidiaSettingsAttribute


@dataclass(frozen=True, slots=True)
class NvidiaSettingsPerformanceMode:
    level: int
    graphics_maximum: int | None
    graphics_editable: bool | None
    memory_transfer_editable: bool | None


def query_settings_output(
    session: NvidiaSettingsSession, target: str, *, deadline: MonotonicDeadline | None = None
) -> str:
    if not isinstance(session, NvidiaSettingsSession):
        raise ValidationError("NVIDIA settings query session is invalid.")
    executable = session.query.executable
    if executable.state != GpuExecutableState.FOUND or executable.path is None:
        raise StateError("NVIDIA settings trusted executable is unavailable.")
    timeout = 2 if deadline is None else int(min(2, deadline.remaining_seconds()))
    if timeout < 1:
        raise TimeoutError("NVIDIA settings query deadline expired.")
    result = session.query.capture(
        [executable.path, "-c", session.display, "-q", target],
        timeout=timeout,
        env=display_process_environment(session.display, session.xauthority),
    )
    require_command_result(
        result, error_message="NVIDIA settings query returned a malformed native response."
    )
    if deadline is not None and deadline.expired():
        raise TimeoutError("NVIDIA settings query completed after its deadline.")
    if result.return_code != 0:
        raise StateError(
            "NVIDIA settings native query failed.",
            details={
                "target": target,
                "return_code": result.return_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "actuator_invoked": False,
            },
        )
    return result.stdout


def parse_settings_attribute(
    output: str,
    *,
    attribute: str,
    target_type: Literal["gpu", "fan"],
    target_id: int,
) -> NvidiaSettingsAttribute:
    expression = (
        rf"(?m)^\s*Attribute '{re.escape(attribute)}' "
        rf"\([^\n]*\[{target_type}:{target_id}\]\):\s*(-?\d+)\.\s*$"
    )
    values = re.findall(expression, output)
    if len(values) != 1:
        raise ValidationError("NVIDIA settings actual attribute is absent or ambiguous.")
    ranges = re.findall(
        rf"valid values for '{re.escape(attribute)}' are in the range\s+(-?\d+)\s+-\s+(-?\d+)",
        output,
    )
    if len(ranges) > 1:
        raise ValidationError("NVIDIA settings native range is ambiguous.")
    minimum, maximum = (int(ranges[0][0]), int(ranges[0][1])) if ranges else (None, None)
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValidationError("NVIDIA settings native range is reversed.")
    return NvidiaSettingsAttribute(int(values[0]), minimum, maximum)


def query_settings_fans(
    session: NvidiaSettingsSession,
    *,
    native_gpu_id: int,
    deadline: MonotonicDeadline | None = None,
) -> tuple[NvidiaSettingsFan, ...]:
    output = query_settings_output(
        session, f"[gpu:{native_gpu_id}.fan]/GPUTargetFanSpeed", deadline=deadline
    )
    blocks = re.split(r"(?=\s*Attribute 'GPUTargetFanSpeed')", output)
    fans: list[NvidiaSettingsFan] = []
    native_ids: set[int] = set()
    for block in blocks:
        if not block.strip():
            continue
        ids = re.findall(r"Attribute 'GPUTargetFanSpeed' \([^\n]*\[fan:(\d+)\]\):", block)
        if len(ids) != 1:
            raise ValidationError("NVIDIA settings related fan response is malformed.")
        native_id = int(ids[0])
        if native_id in native_ids:
            raise ValidationError("NVIDIA settings related fan target is duplicated.")
        observed = parse_settings_attribute(
            block, attribute="GPUTargetFanSpeed", target_type="fan", target_id=native_id
        )
        if observed.minimum is None or observed.maximum is None:
            raise StateError("NVIDIA settings related fan range is unavailable.")
        if not 0 <= observed.minimum <= observed.maximum <= 100:
            raise ValidationError("NVIDIA settings related fan percentage range is invalid.")
        native_ids.add(native_id)
        fans.append(NvidiaSettingsFan(native_id, observed))
    if not fans:
        raise StateError("NVIDIA settings related fan target is unavailable.")
    return tuple(fans)


def query_settings_performance_modes(
    session: NvidiaSettingsSession, *, native_gpu_id: int
) -> tuple[NvidiaSettingsPerformanceMode, ...]:
    output = query_settings_output(session, f"[gpu:{native_gpu_id}]/GPUPerfModes")
    matches = re.findall(
        rf"(?m)^\s*Attribute 'GPUPerfModes' \([^\n]*\[gpu:{native_gpu_id}\]\):\s*(.+)$",
        output,
    )
    if len(matches) != 1:
        raise ValidationError(
            "NVIDIA settings native performance modes are unavailable or ambiguous."
        )
    modes: list[NvidiaSettingsPerformanceMode] = []
    levels: set[int] = set()
    for row in matches[0].rstrip(". ").split(";"):
        if not row.strip():
            continue
        fields: dict[str, str] = {}
        for token in row.split(","):
            name, separator, value = token.strip().partition("=")
            if not separator or not name or not value or name in fields:
                raise ValidationError(
                    "NVIDIA settings performance token is malformed or duplicated."
                )
            fields[name] = value
        native_level = fields.get("perf")
        if native_level is None or not re.fullmatch(r"\d+", native_level):
            raise ValidationError("NVIDIA settings native performance identity is unavailable.")
        level = int(native_level)
        if level in levels:
            raise ValidationError("NVIDIA settings native performance level is duplicated.")
        for name in ("nvclockeditable", "memtransferrateeditable"):
            if fields.get(name, "0") not in ("0", "1"):
                raise ValidationError("NVIDIA settings performance editability is invalid.")
        maximum_value = fields.get("nvclockmax")
        if maximum_value is not None and not re.fullmatch(r"\d+", maximum_value):
            raise ValidationError("NVIDIA settings performance frequency is invalid.")
        modes.append(
            NvidiaSettingsPerformanceMode(
                level,
                int(maximum_value) if maximum_value is not None else None,
                fields["nvclockeditable"] == "1" if "nvclockeditable" in fields else None,
                (
                    fields["memtransferrateeditable"] == "1"
                    if "memtransferrateeditable" in fields
                    else None
                ),
            )
        )
        levels.add(level)
    if not modes:
        raise StateError("NVIDIA settings native performance modes are unavailable.")
    return tuple(modes)


def invoke_settings_attribute(session: NvidiaSettingsSession, *, target: str, value: int) -> None:
    if not isinstance(session, NvidiaSettingsSession) or not is_strict_int(value):
        raise ValidationError("NVIDIA settings native assignment is invalid.")
    executable = session.query.executable
    if executable.state != GpuExecutableState.FOUND or executable.path is None:
        raise StateError("NVIDIA settings trusted executable is unavailable.")
    response = session.query.capture(
        [executable.path, "-c", session.display, "-a", f"{target}={value}"],
        timeout=2,
        env=display_process_environment(session.display, session.xauthority),
    )
    require_command_result(
        response, error_message="NVIDIA settings native actuator response is malformed."
    )
    if response.return_code != 0:
        raise StateError(
            "NVIDIA settings native actuator failed.",
            details={
                "stdout": response.stdout,
                "stderr": response.stderr,
                "return_code": response.return_code,
                "actuator_invoked": True,
            },
        )
