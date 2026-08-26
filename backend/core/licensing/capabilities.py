"""SoAI - Closed licensing capability validation [backend/core/licensing/capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue

LICENSING_CAPABILITIES = frozenset(
    (
        "personal_noncommercial",
        "organization_evaluation",
        "organization_internal",
        "modification",
        "consulting_client_delivery",
        "hosted_service",
        "managed_service",
        "redistribution",
        "oem",
        "sublicensing",
        "trademark_use",
    )
)


def require_licensing_capabilities(value: JSONValue) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValidationError("Licensing capabilities are invalid.")
    capabilities_list: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValidationError("Licensing capabilities are invalid.")
        capabilities_list.append(item)
    capabilities = tuple(capabilities_list)
    if list(capabilities) != sorted(set(capabilities)) or any(
        item not in LICENSING_CAPABILITIES for item in capabilities
    ):
        raise ValidationError("Licensing capabilities must be closed, sorted, and unique.")
    return capabilities


def require_commercial_licensing_capabilities(capabilities: tuple[str, ...]) -> None:
    if "organization_evaluation" in capabilities or not any(
        capability != "personal_noncommercial" for capability in capabilities
    ):
        raise ValidationError("Commercial licensing capabilities are invalid.")


__all__ = (
    "LICENSING_CAPABILITIES",
    "require_commercial_licensing_capabilities",
    "require_licensing_capabilities",
)
