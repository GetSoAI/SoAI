"""SoAI - Memory API schemas [backend/features/api/schemas/memory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import StrictStr, field_validator, model_validator

from core.memory.revisions import memory_management_error
from core.meta.soai_v1 import SoAIV1StrictModel
from core.serialization.sha256_hexdigest import is_canonical_sha256_hexdigest

__all__ = ("ChatMemoryProfileUpdate",)


class ChatMemoryProfileUpdate(SoAIV1StrictModel):
    expected_revision: StrictStr | None = None
    preferred_name: str | None = None
    assistant_name: str | None = None
    role_background: str | None = None
    current_goals: str | None = None
    preferences: str | None = None
    dislikes_to_avoid: str | None = None
    communication_style: str | None = None
    recurring_tools_projects: str | None = None
    extra_notes: str | None = None


class MemoryObservationUpdate(SoAIV1StrictModel):
    id: StrictStr | None
    content: StrictStr


class MemoryEntryCreate(SoAIV1StrictModel):
    id: StrictStr
    name: StrictStr
    content: StrictStr


class MemoryRevisionPrecondition(SoAIV1StrictModel):
    expected_revision: StrictStr

    @field_validator("expected_revision")
    @classmethod
    def validate_revision(cls, value: str) -> str:
        if not is_canonical_sha256_hexdigest(value):
            raise memory_management_error(
                "memory_invalid_revision",
                "Refresh the library to obtain a valid memory revision.",
                422,
            )
        return value


class MemoryEntryUpdate(MemoryRevisionPrecondition):
    name: StrictStr | None = None
    observation: MemoryObservationUpdate | None = None

    @model_validator(mode="after")
    def validate_update(self) -> MemoryEntryUpdate:
        if self.name is None and self.observation is None:
            raise memory_management_error(
                "memory_invalid_update", "Provide a title or an observation to update.", 422
            )
        if ("name" in self.model_fields_set and self.name is None) or (
            "observation" in self.model_fields_set and self.observation is None
        ):
            raise memory_management_error(
                "memory_invalid_update",
                "Omit unchanged fields rather than setting them to null.",
                422,
            )
        return self


class MemoryRelationUpdate(MemoryRevisionPrecondition):
    from_entity_id: StrictStr
    to_entity_id: StrictStr
    relation_type: StrictStr
