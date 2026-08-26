"""SoAI - JSON object field extraction helpers [backend/core/validation/json_object_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Collection

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, is_json_dict

__all__ = (
    "extract_known_json_object_fields",
    "extract_known_json_object_fields_from_section",
    "require_optional_json_object_section",
    "validate_allowed_json_object_fields",
)


def extract_known_json_object_fields(payload: JSONDict, field_names: Collection[str]) -> JSONDict:
    extracted: JSONDict = {}
    for field_name in field_names:
        if field_name in payload:
            extracted[field_name] = payload.get(field_name)
    return extracted


def extract_known_json_object_fields_from_section(
    payload: JSONDict,
    *,
    section_name: str,
    field_names: Collection[str],
) -> JSONDict:
    extracted: JSONDict = {}
    section_value = require_optional_json_object_section(payload, section_name=section_name)
    if section_value is None:
        return extracted
    validate_allowed_json_object_fields(
        section_value,
        allowed_field_names=field_names,
        label=section_name,
    )
    for field_name in field_names:
        if field_name in section_value:
            extracted[field_name] = section_value.get(field_name)
    return extracted


def require_optional_json_object_section(
    payload: JSONDict,
    *,
    section_name: str,
) -> JSONDict | None:
    section_value = payload.get(section_name)
    if section_value is None:
        return None
    if not is_json_dict(section_value):
        raise ValidationError(f"{section_name} must be an object.")
    return section_value


def validate_allowed_json_object_fields(
    payload: JSONDict,
    *,
    allowed_field_names: Collection[str],
    label: str,
) -> None:
    invalid_fields = sorted(set(payload.keys()) - set(allowed_field_names))
    if invalid_fields:
        invalid_fields_text = ", ".join(invalid_fields)
        raise ValidationError(f"Unsupported {label} fields: {invalid_fields_text}.")
