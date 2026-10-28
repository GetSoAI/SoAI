"""SoAI - Static backend variant resource validation [backend/core/plugins/backend_variant_resources.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.plugins.backend_variant_option_validation import require_backend_variant_options
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.serialization.json_parsing import MAX_JSON_NESTING_DEPTH, parse_json_value
from core.types.json import JSONDict, is_json_dict

__all__ = (
    "MAX_BACKEND_VARIANT_RESOURCE_BYTES",
    "parse_backend_variant_resource",
    "require_backend_variant_resource_name",
)

MAX_BACKEND_VARIANT_RESOURCE_BYTES = 1024 * 1024


def require_backend_variant_resource_name(value: str) -> str:
    if not value.endswith(".json"):
        raise ValidationError("Backend variant metadata must reference a root JSON resource.")
    require_portable_plugin_identifier(value[:-5], field_name="backend variant resource")
    return value


def parse_backend_variant_resource(content: bytes) -> list[JSONDict]:
    if len(content) > MAX_BACKEND_VARIANT_RESOURCE_BYTES:
        raise ValidationError("Backend variant metadata exceeds 1 MiB.")
    parsed = parse_json_value(
        content,
        field="Backend variant metadata",
        max_depth=MAX_JSON_NESTING_DEPTH,
        strict_utf8=True,
        reject_duplicate_keys=True,
    )
    require_backend_variant_options(parsed, field_name="BACKEND_VARIANT_OPTIONS")
    if not isinstance(parsed, list) or not all(is_json_dict(option) for option in parsed):
        raise ValidationError("Backend variant metadata must contain a list of option objects.")
    return [option for option in parsed if is_json_dict(option)]
