"""SoAI - Model parameter schema normalization for reload checks [backend/models/parameters/schema_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

    type ParameterSchema = dict[str, JSONDict]

__all__ = ("normalize_parameter_schema",)


def normalize_parameter_schema(schema: JSONDict) -> ParameterSchema:
    normalized: ParameterSchema = {}
    for key, value in schema.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        normalized[key] = value
    return normalized
