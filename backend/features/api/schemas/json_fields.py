"""SoAI - Pydantic JSON field aliases [backend/features/api/schemas/json_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic.types import JsonValue

from core.types.json import JSONValue

PydanticJSONValue = JSONValue
if not TYPE_CHECKING:
    PydanticJSONValue = JsonValue

__all__ = ("PydanticJSONValue",)
