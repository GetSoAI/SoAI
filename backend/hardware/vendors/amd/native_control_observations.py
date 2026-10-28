"""SoAI - Strong AMD physical sysfs control originals and native domains [backend/hardware/vendors/amd/native_control_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_settings_contract import AMD_NATIVE_PERFORMANCE_MODES
from core.validation.strict_integer import is_strict_int
from hardware.vendors.amd.overdrive_observations import (
    AmdOverdriveObservation,
    parse_amd_overdrive_observation,
)
from hardware.vendors.amd.physical_binding import AmdBoundDevice, acquire_amd_physical_binding

if TYPE_CHECKING:
    from core.hardware.gpu_physical_identity import GPUPhysicalDevice
    from core.system.protocols import CommandExecutorProtocol

__all__ = (
    "AmdPowerDomain",
    "AmdFanDomain",
    "AmdNativeControlState",
    "acquire_amd_control_state",
)

_READ_CONTROL_SCRIPT = """
set -eu
root="$1"
test -d "$root"
for relative in uevent power_dpm_force_performance_level pp_od_clk_voltage; do
    test "$relative" = uevent || test "$4" = 1 || continue
    if test -e "$root/$relative"; then
        printf 'BEGIN %s\n' "$relative"
        cat -- "$root/$relative"
        printf '\nEND\n'
    fi
done
for directory in "$root"/hwmon/hwmon*; do
    test -d "$directory" || continue
    for file in "$directory"/name "$directory"/power*_cap* "$directory"/pwm*; do
        test -e "$file" || continue
        case "${file##*/}" in
            power*) test "$2" = 1 || continue ;;
            pwm*) test "$3" = 1 || continue ;;
        esac
        relative="${file#"$root"/}"
        printf 'BEGIN %s\n' "$relative"
        cat -- "$file"
        printf '\nEND\n'
    done
done
"""


@dataclass(frozen=True, slots=True)
class AmdPowerDomain:
    native_id: int
    current: int
    minimum: int
    maximum: int
    default: int | None
    path: str


@dataclass(frozen=True, slots=True)
class AmdFanDomain:
    native_id: int
    policy: int
    observed_pwm: int | None
    minimum: int
    maximum: int
    path: str
    policy_path: str


@dataclass(frozen=True, slots=True)
class AmdNativeControlState:
    bound: AmdBoundDevice
    power_domains: tuple[AmdPowerDomain, ...]
    fans: tuple[AmdFanDomain, ...]
    overdrive: AmdOverdriveObservation | None
    performance_mode: str | None
    performance_path: str


def acquire_amd_control_state(
    executor: CommandExecutorProtocol, *, target: GPUPhysicalDevice, fields: tuple[str, ...]
) -> AmdNativeControlState:
    if (
        not isinstance(fields, tuple)
        or not fields
        or not set(fields).issubset(
            {"power_limit", "fan_speed", "core_clock", "mem_clock", "performance_mode"}
        )
    ):
        raise ValidationError("AMD native query requires its explicit selected field scope.")
    bound = acquire_amd_physical_binding(executor, target=target)
    observed_pci = bound.device.identity.pci_bdf_full
    pci = normalize_observed_full_pci_bdf(observed_pci) if observed_pci is not None else None
    if pci is None:
        raise StateError("AMD sysfs controls require the actual complete physical PCI relation.")
    root = f"/sys/bus/pci/devices/{observed_pci}"
    result = executor.execute(
        [
            "sh",
            "-c",
            _READ_CONTROL_SCRIPT,
            "soai-amd-control-query",
            root,
            "1" if "power_limit" in fields else "0",
            "1" if "fan_speed" in fields else "0",
            "1" if set(fields) & {"core_clock", "mem_clock", "performance_mode"} else "0",
        ],
        timeout=5,
        shell=False,
        use_sudo=False,
    )
    if (
        not is_strict_int(result.return_code)
        or not isinstance(result.stdout, str)
        or not isinstance(result.stderr, str)
    ):
        raise ValidationError("AMD native control query returned a malformed response.")
    if result.return_code != 0:
        raise StateError(
            "AMD native control query failed.",
            details={
                "return_code": result.return_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "actuator_invoked": False,
            },
        )
    try:
        return _interpret_control_state(bound, root, pci, result.stdout)
    except (StateError, ValidationError) as exception:
        error_type = StateError if isinstance(exception, StateError) else ValidationError
        raise error_type(
            "AMD actual native control observation is invalid or unavailable.",
            details={"stdout": result.stdout, "stderr": result.stderr, "actuator_invoked": False},
            cause=exception,
        ) from exception


def _interpret_control_state(
    bound: AmdBoundDevice, root: str, pci: str, output: str
) -> AmdNativeControlState:
    sections = _parse_sections(output)
    uevent = sections.get("uevent")
    if uevent is None:
        raise StateError("AMD native control path has no actual PCI identity.")
    identity: dict[str, str] = {}
    for line in uevent.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            if key in identity:
                raise ValidationError("AMD actual sysfs identity contains duplicate fields.")
            identity[key] = value
    vendor_id = identity.get("PCI_ID", "").split(":")
    if (
        normalize_observed_full_pci_bdf(identity.get("PCI_SLOT_NAME", "")) != pci
        or len(vendor_id) != 2
        or vendor_id[0].casefold() != "1002"
    ):
        raise StateError("AMD native control path conflicts with actual physical identity.")
    monitors = tuple(
        key.removesuffix("/name")
        for key, value in sections.items()
        if key.endswith("/name") and value == "amdgpu"
    )
    if len(monitors) > 1:
        raise StateError("AMD native control domain relation is ambiguous across hwmon instances.")
    if any(
        key.startswith("hwmon/")
        and not key.endswith("/name")
        and not any(key.startswith(f"{monitor}/") for monitor in monitors)
        for key in sections
    ):
        raise StateError("AMD native hwmon controls lack their actual driver relation.")
    powers: list[AmdPowerDomain] = []
    fans: list[AmdFanDomain] = []
    if monitors:
        monitor = monitors[0]
        for key, native_text in sections.items():
            power = re.fullmatch(rf"{re.escape(monitor)}/power(\d+)_cap", key)
            fan = re.fullmatch(rf"{re.escape(monitor)}/pwm(\d+)_enable", key)
            if power:
                current = _number(native_text, minimum=1)
                minimum = _required_number(sections, f"{key}_min", 0)
                maximum = _required_number(sections, f"{key}_max", 1)
                default = (
                    _number(sections[f"{key}_default"], minimum=1)
                    if f"{key}_default" in sections
                    else None
                )
                if (
                    not minimum <= current <= maximum
                    or default is not None
                    and not minimum <= default <= maximum
                ):
                    raise ValidationError(
                        "AMD actual power original/default conflicts with native range."
                    )
                powers.append(
                    AmdPowerDomain(
                        int(power[1]), current, minimum, maximum, default, f"{root}/{key}"
                    )
                )
            if fan:
                policy = _number(native_text, minimum=0)
                if policy not in (0, 1, 2):
                    raise ValidationError("AMD actual fan control policy is invalid.")
                base = key.removesuffix("_enable")
                minimum = (
                    _number(sections[f"{base}_min"], minimum=0) if f"{base}_min" in sections else 0
                )
                maximum = (
                    _number(sections[f"{base}_max"], minimum=0)
                    if f"{base}_max" in sections
                    else 255
                )
                if not 0 <= minimum <= maximum <= 255:
                    raise ValidationError("AMD actual PWM range conflicts with its native ABI.")
                observed = _required_number(sections, base, 0) if policy == 1 else None
                if observed is not None and not minimum <= observed <= maximum:
                    raise ValidationError("AMD observed manual PWM is outside its actual range.")
                fans.append(
                    AmdFanDomain(
                        int(fan[1]),
                        policy,
                        observed,
                        minimum,
                        maximum,
                        f"{root}/{base}",
                        f"{root}/{key}",
                    )
                )
    table = sections.get("pp_od_clk_voltage")
    overdrive = (
        parse_amd_overdrive_observation(table, f"{root}/pp_od_clk_voltage")
        if table is not None
        else None
    )
    performance = sections.get("power_dpm_force_performance_level")
    if performance is not None and performance not in AMD_NATIVE_PERFORMANCE_MODES:
        raise ValidationError("AMD actual performance policy is invalid.")
    return AmdNativeControlState(
        bound,
        tuple(powers),
        tuple(fans),
        overdrive,
        performance,
        f"{root}/power_dpm_force_performance_level",
    )


def _parse_sections(output: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    name: str | None = None
    lines: list[str] = []
    for line in output.splitlines():
        if line.startswith("BEGIN "):
            if name is not None:
                raise ValidationError("AMD native control sections are nested.")
            name = line.removeprefix("BEGIN ")
            if (
                not re.fullmatch(
                    r"(?:uevent|pp_od_clk_voltage|power_dpm_force_performance_level|hwmon/hwmon\d+/[a-z][a-z0-9_]*)",
                    name,
                )
                or name in sections
            ):
                raise ValidationError(
                    "AMD native control section identity is invalid or duplicated."
                )
            lines = []
        elif line == "END":
            if name is None:
                raise ValidationError("AMD native control section has no declared identity.")
            sections[name] = "\n".join(lines).strip()
            name = None
        elif name is not None:
            lines.append(line)
        elif line.strip():
            raise ValidationError("AMD native control response contains unowned data.")
    if name is not None:
        raise ValidationError("AMD native control response is incomplete.")
    return sections


def _number(value: str, *, minimum: int) -> int:
    if not re.fullmatch(r"[0-9]+", value):
        raise ValidationError("AMD native control scalar is invalid.")
    number = int(value)
    if number < minimum:
        raise ValidationError("AMD native control scalar is outside its actual domain.")
    return number


def _required_number(values: dict[str, str], key: str, minimum: int) -> int:
    if key not in values:
        raise StateError(
            "AMD native control constraint or original is unavailable.",
            details={"native_member": key},
        )
    return _number(values[key], minimum=minimum)
