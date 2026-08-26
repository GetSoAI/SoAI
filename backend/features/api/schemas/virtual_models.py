"""SoAI - Virtual model routing schemas [backend/features/api/schemas/virtual_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from core.errors.exceptions import ValidationError
from features.api.schemas.json_fields import PydanticJSONValue

__all__ = (
    "ConstituentModel",
    "VirtualModelCreate",
    "VirtualModelEnabledUpdate",
    "VirtualModelUpdate",
)


class ConstituentModel(BaseModel):
    universal_id: str
    parameters: dict[str, PydanticJSONValue] | None = None


class VirtualModelCreate(BaseModel):
    name: str
    strategy: Literal["load_balancing", "failover"]
    models: list[ConstituentModel] = Field(...)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = (value or "").strip()
        if not name:
            raise ValidationError("Name cannot be empty or contain only whitespace.")
        if not re.search("[a-zA-Z0-9]", name):
            raise ValidationError("Name must include at least one alphanumeric character.")
        if not re.match("^[a-zA-Z0-9/._ -]+$", name):
            raise ValidationError(
                "Name can only contain alphanumeric characters, spaces, slash, underscore, dot, and hyphen.",
            )
        return name

    @field_validator("models")
    @classmethod
    def check_unique_universal_ids(cls, models: list[ConstituentModel]) -> list[ConstituentModel]:
        if not models or len(models) < 2:
            raise ValidationError("At least two constituent models must be provided.")
        if len(models) != len({model.universal_id for model in models}):
            raise ValidationError("Duplicate universal_id found in constituent models list.")
        return models


class VirtualModelUpdate(BaseModel):
    strategy: Literal["load_balancing", "failover"] | None = None
    models: list[ConstituentModel] | None = Field(None)

    @field_validator("models")
    @classmethod
    def check_unique_universal_ids(
        cls,
        models: list[ConstituentModel] | None,
    ) -> list[ConstituentModel] | None:
        if models is not None:
            if len(models) < 2:
                raise ValidationError(
                    "At least two constituent models must be provided when updating the list.",
                )
            if len(models) != len({model.universal_id for model in models}):
                raise ValidationError("Duplicate universal_id found in constituent models list.")
        return models


class VirtualModelEnabledUpdate(BaseModel):
    enabled: bool
