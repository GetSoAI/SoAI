"""SoAI - AMD SMI per-card payload selection [backend/hardware/vendors/amd/amd_smi_payload_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from hardware.vendors.amd.amd_smi_parsing import extract_amd_smi_text

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "collect_amd_smi_gpu_payloads",
    "looks_like_amd_smi_gpu_payload",
    "select_amd_smi_gpu_entry_for_card",
    "select_amd_smi_payload_for_card",
)

AMD_SMI_GPU_PAYLOAD_MARKERS: frozenset[str] = frozenset(
    {"asic", "bus", "vram", "limit", "clock", "driver"},
)


def looks_like_amd_smi_gpu_payload(payload: Mapping[str, JSONValue]) -> bool:
    present = {key.lower() for key in payload if isinstance(key, str)}
    return bool(present & AMD_SMI_GPU_PAYLOAD_MARKERS)


def collect_amd_smi_gpu_payloads(payload: JSONValue | None) -> list[JSONDict]:
    entries: list[JSONDict] = []
    if isinstance(payload, Mapping):
        if looks_like_amd_smi_gpu_payload(payload):
            entries.append({str(key): value for key, value in payload.items()})
            return entries
        for value in payload.values():
            entries.extend(collect_amd_smi_gpu_payloads(value))
    elif isinstance(payload, list):
        for value in payload:
            entries.extend(collect_amd_smi_gpu_payloads(value))
    return entries


def select_amd_smi_gpu_entry_for_card(
    payload: JSONValue | None,
    card_index: int,
) -> JSONDict | None:
    entries = collect_amd_smi_gpu_payloads(payload)
    if not entries:
        return None
    indexed_entries = _collect_indexed_payloads(payload, card_index) if payload is not None else []
    selected = _first_gpu_payload(indexed_entries)
    if selected is not None:
        return selected
    if len(entries) == 1:
        return entries[0]
    if 0 <= card_index < len(entries):
        return entries[card_index]
    return None


def select_amd_smi_payload_for_card(
    payload: JSONValue | None,
    static_entry: JSONDict,
    card_index: int,
    total_cards: int,
) -> JSONValue | None:
    if payload is None:
        return None
    static_identity_values = _identity_values(static_entry)
    if static_identity_values:
        for candidate in _collect_mapping_payloads(payload):
            selected = _first_gpu_payload([candidate])
            if selected is None:
                continue
            selected_identity_values = _identity_values(selected)
            if static_identity_values.intersection(selected_identity_values):
                return selected
    indexed_entries = _collect_indexed_payloads(payload, card_index)
    if indexed_entries:
        selected = _first_gpu_payload(indexed_entries)
        return selected if selected is not None else indexed_entries[0]
    entries = collect_amd_smi_gpu_payloads(payload)
    if len(entries) == 1:
        return entries[0]
    if len(entries) == total_cards and 0 <= card_index < len(entries):
        return entries[card_index]
    return payload if total_cards == 1 else None


def _first_gpu_payload(candidates: list[JSONDict]) -> JSONDict | None:
    for candidate in candidates:
        if looks_like_amd_smi_gpu_payload(candidate):
            return candidate
        nested = collect_amd_smi_gpu_payloads(candidate)
        if len(nested) == 1:
            return nested[0]
    return None


def _collect_mapping_payloads(payload: JSONValue) -> list[JSONDict]:
    entries: list[JSONDict] = []
    if isinstance(payload, Mapping):
        for value in payload.values():
            entries.extend(_collect_mapping_payloads(value))
        entries.append({str(key): value for key, value in payload.items()})
    elif isinstance(payload, list):
        for value in payload:
            entries.extend(_collect_mapping_payloads(value))
    return entries


def _collect_indexed_payloads(payload: JSONValue, card_index: int) -> list[JSONDict]:
    entries: list[JSONDict] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if isinstance(value, Mapping):
                if _key_matches_card_index(str(key), card_index):
                    entries.append(
                        {str(item_key): item_value for item_key, item_value in value.items()},
                    )
                entries.extend(_collect_indexed_payloads(value, card_index))
            elif isinstance(value, list):
                entries.extend(_collect_indexed_payloads(value, card_index))
    elif isinstance(payload, list):
        for value in payload:
            entries.extend(_collect_indexed_payloads(value, card_index))
    return entries


def _key_matches_card_index(key: str, card_index: int) -> bool:
    normalized = key.strip().lower()
    if normalized == str(card_index):
        return True
    if normalized in (
        f"gpu{card_index}",
        f"gpu_{card_index}",
        f"card{card_index}",
        f"card_{card_index}",
    ):
        return True
    tokens = (
        normalized.replace("_", " ").replace("-", " ").replace(":", " ").replace(".", " ").split()
    )
    return any(token == str(card_index) for token in tokens) and (
        "gpu" in normalized or "card" in normalized
    )


def _identity_values(payload: JSONDict) -> set[str]:
    values: set[str] = set()
    for candidates in (
        (("uuid",),),
        (("bdf",),),
        (("asic", "serial"),),
        (("product", "serial"),),
    ):
        value = extract_amd_smi_text(payload, candidates)
        if value is not None:
            values.add(value)
    return values
