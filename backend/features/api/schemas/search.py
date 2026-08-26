"""SoAI - Search result schemas [backend/features/api/schemas/search.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.conversations.archived_conversation_models import (
    ArchivedConversationSettingsAuthority,
)
from core.errors.exceptions import ValidationError

__all__ = (
    "SearchResultConversation",
    "SearchResultDevice",
    "SearchResultModel",
    "SearchResultPlugin",
    "SearchResultPrompt",
    "SearchResults",
)


class SearchResultPlugin(BaseModel):
    name: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    version_soaiplugin: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)


class SearchResultModel(BaseModel):
    universal_id: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    plugin: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)


class SearchResultDevice(BaseModel):
    type: str = Field(
        ...,
        min_length=1,
        description="Device category identifier (e.g., CPU, GPU, VOLUME, NETWORK).",
    )
    name: str = Field(..., min_length=1)
    id: int | str = Field(..., description="Primary identifier for the device.")
    component: str = Field(
        ...,
        min_length=1,
        description="Normalized component slug used by the WebUI (cpu, gpu, disk, network).",
    )
    identifier: str | None = Field(
        default=None,
        description="Component-specific identifier used for detail navigation (mount path, interface name, GPU index, etc.).",
    )
    model_config = ConfigDict(extra="allow")

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: int | str) -> int | str:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValidationError("Device search result id must be non-empty.")
            return stripped
        return value


class SearchResultConversation(BaseModel):
    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    last_modified_at_ms: int = Field(..., ge=0)
    color: str | None = None
    is_favorite: bool = False
    is_automation: bool = False
    is_messaging: bool = False
    messaging_platform: str | None = None
    messaging_account_label: str | None = None
    messaging_account_snapshot_id: str | None = None
    settings_authority: ArchivedConversationSettingsAuthority


class SearchResultPrompt(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    modified_at_ms: int = Field(..., ge=0)
    color: str | None = None


class SearchResults(BaseModel):
    plugins: list[SearchResultPlugin] = Field(default_factory=list[SearchResultPlugin])
    models: list[SearchResultModel] = Field(default_factory=list[SearchResultModel])
    devices: list[SearchResultDevice] = Field(default_factory=list[SearchResultDevice])
    conversations: list[SearchResultConversation] = Field(
        default_factory=list[SearchResultConversation],
    )
    prompts: list[SearchResultPrompt] = Field(default_factory=list[SearchResultPrompt])
