"""SoAI - Configuration patch schemas [backend/features/api/schemas/configs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel

from features.api.schemas.json_fields import PydanticJSONValue

__all__ = ("ConfigPatch",)


class ConfigPatch(BaseModel):
    changes: dict[str, PydanticJSONValue]
