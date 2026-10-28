"""SoAI - Agent turn lifecycle noncritical logging [backend/features/agent/runtime/turn_lifecycle/noncritical_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_noncritical_turn_details",)


def build_noncritical_turn_details(
    *,
    conv_id: str,
    turn_id: str,
    context_message: str,
    request_id: str | None,
) -> JSONDict:
    details: JSONDict = {
        "conv_id": conv_id,
        "turn_id": turn_id,
        "context_message": context_message,
    }
    if request_id is not None:
        details["request_id"] = request_id
    return details
