"""SoAI - AMD SMI payload parsing [backend/hardware/vendors/amd/amd_smi_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.validation.coercion import coerce_int_from_scalar
from core.validation.text_numbers import coerce_float_from_text

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_amd_smi_clock_caps",
    "extract_amd_smi_numeric",
    "extract_amd_smi_processes",
    "extract_amd_smi_text",
    "parse_amd_smi_clock_levels",
    "select_amd_smi_level",
)


def _normalized_key(value: str) -> str:
    return re.sub("[^a-z0-9]+", "_", value.lower()).strip("_")


def _key_matches(key: str, candidates: Sequence[tuple[str, ...]]) -> bool:
    normalized = _normalized_key(key)
    return any(all(token in normalized for token in tokens) for tokens in candidates)


def _iter_values(
    payload: JSONValue | None,
    prefix: str = "",
) -> list[tuple[str, JSONValue]]:
    values: list[tuple[str, JSONValue]] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = key if isinstance(key, str) else str(key)
            path = f"{prefix}_{key_text}" if prefix else key_text
            values.append((path, value))
            values.extend(_iter_values(value, path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            path = f"{prefix}_{index}" if prefix else str(index)
            values.extend(_iter_values(value, path))
    return values


def extract_amd_smi_text(
    payload: JSONValue | None,
    candidates: Sequence[tuple[str, ...]],
) -> str | None:
    for key, value in _iter_values(payload):
        if _key_matches(key, candidates) and isinstance(value, str):
            text = value.strip()
            if text and text.upper() != "N/A":
                return text
    return None


def extract_amd_smi_numeric(
    payload: JSONValue | None,
    candidates: Sequence[tuple[str, ...]],
) -> float | None:
    for key, value in _iter_values(payload):
        if not _key_matches(key, candidates):
            continue
        if isinstance(value, str):
            numeric = coerce_float_from_text(value, allow_bool=False)
        elif isinstance(value, int | float) and not isinstance(value, bool):
            numeric = float(value)
        else:
            numeric = None
        if numeric is not None:
            return numeric
    return None


def parse_amd_smi_clock_levels(source: JSONValue) -> list[dict[str, int]]:
    entries: list[dict[str, int]] = []
    if isinstance(source, Mapping):
        iterable = list(source.items())
    elif isinstance(source, list):
        iterable = [(str(index), value) for index, value in enumerate(source)]
    else:
        iterable = []
    for key, value in iterable:
        key_text = key if isinstance(key, str) else str(key)
        level_match = re.search(r"(\d+)", key_text)
        level = coerce_int_from_scalar(level_match.group(1)) if level_match else None
        frequency = (
            coerce_int_from_scalar(value)
            if isinstance(value, int | float) and not isinstance(value, bool)
            else coerce_int_from_scalar(coerce_float_from_text(str(value), allow_bool=False))
        )
        if level is None or frequency is None:
            continue
        entries.append({"level": level, "mhz": frequency})
    return sorted(entries, key=lambda item: item["level"])


def _find_clock_section(payload: JSONValue | None, names: Sequence[str]) -> JSONDict | None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if (
                isinstance(key, str)
                and _normalized_key(key) in names
                and isinstance(value, Mapping)
            ):
                return {str(item_key): item_value for item_key, item_value in value.items()}
            nested = _find_clock_section(value, names)
            if nested is not None:
                return nested
    if isinstance(payload, list):
        for value in payload:
            nested = _find_clock_section(value, names)
            if nested is not None:
                return nested
    return None


def build_amd_smi_clock_caps(payload: JSONValue | None, names: Sequence[str]) -> JSONDict:
    section = _find_clock_section(payload, names)
    if section is None:
        return {"supported": False}
    levels = parse_amd_smi_clock_levels(section.get("FREQUENCY_LEVELS"))
    if not levels:
        return {"supported": False}
    frequencies = [entry["mhz"] for entry in levels]
    current_level = coerce_int_from_scalar(section.get("CURRENT LEVEL"))
    current = next(
        (entry["mhz"] for entry in levels if entry["level"] == current_level),
        frequencies[-1],
    )
    return {
        "supported": True,
        "min": min(frequencies),
        "max": max(frequencies),
        "default": max(frequencies),
        "current": current,
        "levels": levels,
    }


def extract_amd_smi_processes(payload: JSONValue | None) -> list[JSONDict]:
    processes: list[JSONDict] = []
    seen_pids: set[int] = set()
    _collect_amd_smi_processes(payload, processes, seen_pids)
    return processes


def _collect_amd_smi_processes(
    payload: JSONValue | None,
    processes: list[JSONDict],
    seen_pids: set[int],
) -> None:
    if isinstance(payload, Mapping):
        pid = coerce_int_from_scalar(payload.get("pid") or payload.get("PID"))
        if pid is not None:
            if pid in seen_pids:
                return
            seen_pids.add(pid)
            name = extract_amd_smi_text(payload, (("process", "name"), ("name",))) or str(pid)
            memory = extract_amd_smi_numeric(payload, (("memory",), ("vram",)))
            processes.append(
                {
                    "pid": pid,
                    "name": name,
                    "used_memory_mb": int(memory) if memory is not None else 0,
                },
            )
            return
        for value in payload.values():
            _collect_amd_smi_processes(value, processes, seen_pids)
    elif isinstance(payload, list):
        for value in payload:
            _collect_amd_smi_processes(value, processes, seen_pids)


def select_amd_smi_level(levels: Sequence[Mapping[str, JSONValue]], target: int) -> tuple[int, int]:
    candidates: list[tuple[int, int]] = []
    for entry in levels:
        level = coerce_int_from_scalar(entry.get("level"))
        mhz = coerce_int_from_scalar(entry.get("mhz"))
        if level is not None and mhz is not None:
            candidates.append((level, mhz))
    if not candidates:
        raise ValueError("No AMD SMI clock levels are available.")
    return min(candidates, key=lambda item: abs(item[1] - target))
