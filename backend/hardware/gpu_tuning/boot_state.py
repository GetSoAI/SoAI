"""SoAI - GPU slot boot-state payload helpers [backend/hardware/gpu_tuning/boot_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.validation.boolean_coercion import coerce_bool_flag
from hardware.control.profiles import default_boot_payload

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "boot_enabled",
    "boot_payload_from_value",
    "disabled_boot_payload",
    "enabled_boot_payload",
    "pending_enabled_boot_payload",
    "slot_toggle_enabled_boot_payload",
)


def disabled_boot_payload() -> JSONDict:
    return default_boot_payload()


def boot_payload_from_value(value: JSONValue) -> JSONDict:
    return copy.deepcopy(value) if isinstance(value, dict) else default_boot_payload()


def boot_enabled(
    boot_payload: JSONDict,
    *,
    logger: LoggerProtocol,
    operation: str,
) -> bool:
    return coerce_bool_flag(
        boot_payload.get("enabled"),
        logger=logger,
        operation=operation,
        default=False,
        recover_message="Failed to parse boolean flag (non-critical).",
    )


def enabled_boot_payload(
    *,
    slot_id: str,
    applied_signature: JSONValue,
    applied_at: JSONValue,
) -> JSONDict:
    return {
        "enabled": True,
        "slot": slot_id,
        "applied_signature": applied_signature,
        "applied_at": applied_at,
    }


def pending_enabled_boot_payload(slot_id: str) -> JSONDict:
    return enabled_boot_payload(slot_id=slot_id, applied_signature=None, applied_at=None)


def slot_toggle_enabled_boot_payload(current_boot: JSONDict, slot_id: str) -> JSONDict:
    return enabled_boot_payload(
        slot_id=slot_id,
        applied_signature=current_boot.get("applied_signature"),
        applied_at=current_boot.get("applied_at"),
    )
