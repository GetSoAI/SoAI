"""SoAI - Capability validation result construction [backend/plugins/state/capability_results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "CapabilityValidationResult",
    "create_capability_failure",
    "create_capability_success",
)


@dataclass(frozen=True, slots=True)
class CapabilityValidationResult:
    is_valid: bool
    capability: str
    status: str
    required: JSONValue
    detected: JSONValue
    message: str


def create_capability_failure(
    capability: str,
    status: str,
    required: JSONValue,
    detected: JSONValue,
    message: str,
) -> CapabilityValidationResult:
    return CapabilityValidationResult(
        is_valid=False,
        capability=capability,
        status=status,
        required=required,
        detected=detected,
        message=message,
    )


def create_capability_success(capability: str) -> CapabilityValidationResult:
    return CapabilityValidationResult(
        is_valid=True,
        capability=capability,
        status="supported",
        required=None,
        detected=None,
        message="",
    )
