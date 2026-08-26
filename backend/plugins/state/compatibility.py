"""SoAI - Plugin incompatibility record helpers [backend/plugins/state/compatibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.state.compatibility import (
    CompatibilityInfo,
    IncompatibilityReason,
    can_override_incompatibility,
)
from core.types.json_value import filter_json_mapping
from core.validation.boolean_coercion import coerce_bool_with_recovery

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_compatibility_info",
    "should_block_for_incompatibility",
)

LOGGER_NAME = "SoAI.plugins.state.compatibility"


def build_compatibility_info(
    reason: IncompatibilityReason | None,
    message: str,
    details: Mapping[str, JSONValue] | None,
    override_flag: bool,
) -> CompatibilityInfo:
    normalized_details = filter_json_mapping(details)
    if not reason:
        return CompatibilityInfo(
            reason=None,
            can_override=False,
            is_overridden=False,
            details=normalized_details,
            message=message or "",
        )
    can_override = can_override_incompatibility(reason)
    return CompatibilityInfo(
        reason=reason,
        can_override=can_override,
        is_overridden=bool(override_flag) if can_override else False,
        details=normalized_details,
        message=message,
    )


def should_block_for_incompatibility(
    compatibility: CompatibilityInfo,
    record: JSONDict | None,
    hardware_reasons: frozenset[str],
) -> tuple[bool, bool]:
    if not compatibility.reason or compatibility.is_overridden:
        return (False, False)
    is_hardware = compatibility.reason in hardware_reasons
    user_enabled = coerce_bool_with_recovery(
        record or {},
        "user_enabled_once",
        logger=get_logger(LOGGER_NAME),
        operation="plugins.state.compatibility.coerce_compatibility_bool",
        default=False,
        recover_message="Failed to parse compatibility bool flag (non-critical).",
    )
    return (not is_hardware or not user_enabled, is_hardware)
