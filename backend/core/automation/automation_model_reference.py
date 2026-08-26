"""SoAI - Automation model reference validation [backend/core/automation/automation_model_reference.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.automation.automation_constants import AUTOMATION_PAYLOAD_FIELDS
from core.automation.automation_payload_validation import validate_automation_payload
from core.errors.exceptions import ValidationError
from core.models.reference_validation import validate_active_model_reference
from core.types.json import is_json_dict

if TYPE_CHECKING:
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
        VirtualModelServiceProtocol,
    )
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_automation_model_validation_payload",
    "should_validate_automation_update_model_reference",
    "validate_automation_model_settings_reference",
    "validate_automation_payload_model_reference",
)


def build_automation_model_validation_payload(
    current_payload: Mapping[str, JSONValue],
    update_payload: Mapping[str, JSONValue],
) -> JSONDict:
    merged: JSONDict = {}
    for field_name in AUTOMATION_PAYLOAD_FIELDS:
        if field_name in update_payload:
            value = update_payload[field_name]
            merged[field_name] = value
        elif field_name in current_payload:
            merged[field_name] = current_payload[field_name]
    return merged


def should_validate_automation_update_model_reference(
    update_payload: Mapping[str, JSONValue],
) -> bool:
    return "model_settings" in update_payload or update_payload.get("enabled") is True


async def validate_automation_payload_model_reference(
    payload: Mapping[str, JSONValue],
    *,
    now_ms: int,
    disallowed_unqualified_tools: tuple[str, ...],
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    model_virtual_model_service: VirtualModelServiceProtocol,
) -> JSONDict:
    validated = validate_automation_payload(
        payload,
        now_ms=now_ms,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    )
    model_settings = validated.get("model_settings")
    if not is_json_dict(model_settings):
        raise ValidationError("Automation model_settings must be an object.")
    await validate_automation_model_settings_reference(
        model_settings=model_settings,
        model_resolution_service=model_resolution_service,
        model_information_service=model_information_service,
        model_virtual_model_service=model_virtual_model_service,
    )
    return validated


async def validate_automation_model_settings_reference(
    *,
    model_settings: JSONDict,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    model_virtual_model_service: VirtualModelServiceProtocol,
) -> str:
    model_value = model_settings.get("model")
    if not isinstance(model_value, str) or not model_value.strip():
        raise ValidationError(
            "Automation model_settings.model is required.",
            details={"param": "model_settings.model"},
        )
    model_name = model_value.strip()
    validated = await validate_active_model_reference(
        model_name=model_name,
        model_resolution_service=model_resolution_service,
        model_information_service=model_information_service,
        virtual_model_get=model_virtual_model_service.virtual_model_get,
        unknown_message=f"Automation model_settings.model is unknown: {model_name}",
        disabled_message=f"Automation model_settings.model is disabled: {model_name}",
        details={"param": "model_settings.model"},
    )
    return validated.routing_key
