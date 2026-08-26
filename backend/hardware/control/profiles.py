"""SoAI - Hardware control profiles and slot primitives [backend/hardware/control/profiles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from core.timing.formatting import utc_now_iso
from hardware.gpu_tuning.setting_modes import normalize_field_modes_for_settings

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "compute_slot_signature",
    "default_boot_payload",
    "normalize_slot_identifier",
    "sanitize_slot_entry",
)

GPU_SLOT_IDS: tuple[str, ...] = ("1", "2", "3")
GPU_SLOT_FILE_VERSION = 1


def default_boot_payload() -> JSONDict:
    return {
        "enabled": False,
        "slot": None,
        "applied_signature": None,
        "applied_at": None,
    }


def compute_slot_signature(
    settings: Mapping[str, JSONValue],
    field_modes: Mapping[str, JSONValue] | None = None,
) -> str:
    serialized = serialize_json_compact_stable(
        {
            "settings": settings,
            "field_modes": normalize_field_modes_for_settings(
                settings,
                field_modes if isinstance(field_modes, dict) else None,
            ),
        },
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def sanitize_slot_entry(entry: JSONValue) -> JSONDict | None:
    if not isinstance(entry, dict):
        return None
    settings = entry.get("settings")
    if not isinstance(settings, dict) or not settings:
        return None
    preserved = copy.deepcopy(settings)
    raw_field_modes = entry.get("field_modes")
    field_modes = normalize_field_modes_for_settings(
        preserved,
        raw_field_modes if isinstance(raw_field_modes, dict) else None,
    )
    saved_at = entry.get("saved_at")
    if not isinstance(saved_at, str) or not saved_at:
        saved_at = utc_now_iso()
    last_applied_at = entry.get("last_applied_at")
    if last_applied_at is not None and (not isinstance(last_applied_at, str)):
        last_applied_at = None
    signature = entry.get("signature")
    if not isinstance(signature, str) or not signature:
        signature = compute_slot_signature(preserved, field_modes)
    return {
        "settings": preserved,
        "field_modes": field_modes,
        "saved_at": saved_at,
        "last_applied_at": last_applied_at,
        "signature": signature,
    }


def normalize_slot_identifier(slot: str | int) -> str | None:
    if isinstance(slot, str):
        trimmed = slot.strip()
        if trimmed in GPU_SLOT_IDS:
            return trimmed
        if trimmed.isdigit() and 1 <= (normalized := int(trimmed)) <= len(GPU_SLOT_IDS):
            return str(normalized)
    elif isinstance(slot, int) and 1 <= slot <= len(GPU_SLOT_IDS):
        return str(slot)
    return None
