"""SoAI - Core hardware data types [backend/core/hardware/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("GPUSettingsOutcome",)


@dataclass(frozen=True, slots=True)
class GPUSettingsOutcome:
    success: bool
    status_code: int
    payload: JSONDict
    audit_action: str
    audit_target: str
    audit_details: JSONDict
    error_type: str | None = None
    error_message: str | None = None
    error_detail: JSONDict | None = None
