"""SoAI - Intel GPU capability payload parsing [backend/hardware/vendors/intel/capability_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict, filter_json_dict_list
from core.validation.coercion import coerce_int_from_numberish
from core.validation.text_numbers import coerce_int_from_text

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "IntelFrequencyCapability",
    "extract_intel_config_device",
    "extract_intel_dump_device",
    "parse_frequency_options",
    "resolve_intel_frequency_capability",
)


@dataclass(frozen=True, slots=True)
class IntelFrequencyCapability:
    minimum_mhz: int
    maximum_mhz: int
    current_maximum_mhz: int
    default_mhz: int


def extract_intel_config_device(payload: JSONValue) -> JSONDict:
    if isinstance(payload, dict):
        return dict(payload)
    if isinstance(payload, list):
        for entry in payload:
            device = coerce_json_dict(entry)
            if device is not None:
                return device
    return {}


def extract_intel_dump_device(payload: JSONValue) -> JSONDict:
    root = coerce_json_dict(payload)
    if root is None:
        return {}
    devices = filter_json_dict_list(root.get("devices"))
    return devices[0] if devices else {}


def parse_frequency_options(value: JSONValue) -> list[int]:
    if isinstance(value, str):
        values = [
            parsed
            for part in value.split(",")
            if (parsed := coerce_int_from_text(part.strip())) is not None
        ]
    elif isinstance(value, list):
        values = [
            parsed for item in value if (parsed := coerce_int_from_numberish(item)) is not None
        ]
    else:
        return []
    return sorted({value for value in values if value >= 0})


def resolve_intel_frequency_capability(config_device: JSONDict) -> IntelFrequencyCapability | None:
    tile_entries = filter_json_dict_list(config_device.get("tile_config_data"))
    resolved_minimum: int | None = None
    resolved_maximum: int | None = None
    resolved_current: int | None = None
    for tile in tile_entries:
        options = parse_frequency_options(tile.get("gpu_frequency_valid_options"))
        if len(options) < 2:
            return None
        option_minimum = options[0]
        option_maximum = options[-1]
        current_minimum = coerce_int_from_numberish(tile.get("min_frequency"))
        current_maximum = coerce_int_from_numberish(tile.get("max_frequency"))
        if current_minimum is None or current_maximum is None:
            return None
        if current_minimum < option_minimum or current_maximum > option_maximum:
            return None
        if current_minimum < 0 or current_maximum < 0 or current_minimum >= current_maximum:
            return None
        if option_minimum >= option_maximum:
            return None
        if resolved_minimum is None:
            resolved_minimum = option_minimum
            resolved_maximum = option_maximum
            resolved_current = current_maximum
            continue
        if (
            resolved_minimum != option_minimum
            or resolved_maximum != option_maximum
            or resolved_current != current_maximum
        ):
            return None
    if resolved_minimum is None or resolved_maximum is None or resolved_current is None:
        return None
    return IntelFrequencyCapability(
        minimum_mhz=resolved_minimum,
        maximum_mhz=resolved_maximum,
        current_maximum_mhz=resolved_current,
        default_mhz=resolved_maximum,
    )
