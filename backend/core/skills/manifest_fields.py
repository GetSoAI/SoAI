"""SoAI - Skill compatibility field catalog and value validation [backend/core/skills/manifest_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.skills.errors import build_skill_error
from core.skills.limits import MAX_MANIFEST_BYTES
from core.types.json import JSONDict, JSONValue, is_json_dict, is_str_list
from core.validation.object_fields import require_exact_json_fields
from core.validation.record_fields import require_bool
from core.validation.strings import require_bounded_trimmed_text

__all__ = ("SKILL_BASE_FIELDS", "validate_skill_extension_fields")

SKILL_BASE_FIELDS = frozenset(
    {
        "name",
        "description",
        "license",
        "compatibility",
        "metadata",
        "disable-model-invocation",
        "user-invocable",
    }
)
_EXTENSION_SHAPES = (
    ("argument-hint", "text"),
    ("arguments", "arguments"),
    ("allowed-tools", "text_list"),
    ("disallowed-tools", "text_list"),
    ("tools", "text_list"),
    ("context", "text"),
    ("agent", "text"),
    ("background", "boolean"),
    ("paths", "text_list"),
    ("shell", "text"),
    ("model", "text"),
    ("effort", "text"),
    ("hooks", "object"),
    ("origin", "text"),
    ("homepage", "text"),
    ("author", "text"),
    ("repo", "text"),
    ("tags", "text_list"),
    ("category", "text"),
    ("version", "text"),
)


def validate_skill_extension_fields(payload: JSONDict) -> str:
    require_exact_json_fields(
        payload,
        allowed_fields=SKILL_BASE_FIELDS | dict(_EXTENSION_SHAPES).keys(),
        label="Skill frontmatter; unknown execution fields require a supported compatibility profile",
    )
    extensions = {
        field: value for field, value in payload.items() if field not in SKILL_BASE_FIELDS
    }
    for field, value in extensions.items():
        try:
            _validate_extension_value(field, value)
        except ValidationError as exception:
            raise build_skill_error(
                "skill_invalid_package", reason="invalid_field", field=field
            ) from exception
    return serialize_json_compact_stable_strict(extensions)


def _validate_extension_value(field: str, value: JSONValue) -> None:
    shape = dict(_EXTENSION_SHAPES)[field]
    if shape == "boolean":
        require_bool(value, label=f"Skill {field}", build_error=ValidationError)
        return
    if shape == "object":
        if not is_json_dict(value):
            raise ValidationError(f"Skill {field} must be a JSON object.")
        return
    if shape == "arguments" and is_json_dict(value):
        return
    if shape in {"text_list", "arguments"} and is_str_list(value):
        for item in value:
            _require_text(item, field)
    else:
        _require_text(value, field)


def _require_text(value: JSONValue, field: str) -> None:
    require_bounded_trimmed_text(
        value,
        type_message=f"Skill {field} has an unsupported value type.",
        empty_message=f"Skill {field} must not be blank.",
        max_length=MAX_MANIFEST_BYTES,
        max_length_message=f"Skill {field} exceeds its bounded text limit.",
    )
