"""SoAI - OpenAI request field primitives [backend/core/openai/request_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "require_model_name",
    "resolve_optional_model_name",
)


def resolve_optional_model_name(payload: Mapping[str, JSONValue]) -> str | None:
    return coerce_optional_trimmed_str(payload.get("model"))


def require_model_name(payload: Mapping[str, JSONValue]) -> str:
    model_name = resolve_optional_model_name(payload)
    if model_name is None:
        raise ValidationError("Request missing required field: 'model'.")
    return model_name
