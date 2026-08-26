"""SoAI - WebUI archived conversation schema models [backend/core/conversations/archived_conversation_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = (
    "ArchivedConversationSettingsAuthority",
    "ArchivedConversationSummary",
    "ArchivedConversationsCursor",
    "ArchivedConversationsListRequest",
    "ArchivedConversationsPage",
    "ArchivedConversationsResponse",
    "ArchivedConversationsSearchResponse",
)


class ArchivedConversationSettingsAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["conversation", "automation", "messaging_account"]
    entity_id: str = Field(..., min_length=1)
    entity_label: str = Field(..., min_length=1)
    read_only: bool


class ArchivedConversationSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    last_modified_at_ms: int = Field(..., ge=1)
    color: str | None = Field(default=None, min_length=1)
    is_favorite: bool
    is_automation: bool
    is_messaging: bool
    messaging_platform: str | None = Field(default=None, min_length=1)
    messaging_account_label: str | None = Field(default=None, min_length=1)
    messaging_account_snapshot_id: str | None = Field(default=None, min_length=1)
    is_archived: bool
    settings_authority: ArchivedConversationSettingsAuthority
    message_count: int = Field(..., ge=0)
    compaction_count: int = Field(..., ge=0)
    compaction_tokens_saved: int = Field(..., ge=0)


class ArchivedConversationsCursor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_modified_at_ms: int = Field(..., ge=1)
    id: str = Field(..., min_length=1)


class ArchivedConversationsListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(..., ge=1, le=200)
    before_last_modified_at_ms: int | None = Field(default=None, ge=1)
    before_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_cursor(self) -> ArchivedConversationsListRequest:
        has_last_modified = self.before_last_modified_at_ms is not None
        has_id = self.before_id is not None
        if has_last_modified != has_id:
            raise ValueError(
                "Archived conversation cursor requires both before_last_modified_at_ms and before_id.",
            )
        return self


class ArchivedConversationsPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversations: list[ArchivedConversationSummary] = Field(
        default_factory=list[ArchivedConversationSummary],
    )
    total_count: int = Field(..., ge=0)
    next_cursor: ArchivedConversationsCursor | None = None


class ArchivedConversationsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversations: list[ArchivedConversationSummary] = Field(
        default_factory=list[ArchivedConversationSummary],
    )
    total_count: int = Field(..., ge=0)
    next_cursor: ArchivedConversationsCursor | None = None


class ArchivedConversationsSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversations: list[ArchivedConversationSummary] = Field(
        default_factory=list[ArchivedConversationSummary],
    )
