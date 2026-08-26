"""SoAI - WebUI notification record schema models [backend/core/notifications/notification_record_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.notifications.notification_contracts import (
    NotificationLinkType,
    NotificationType,
)
from core.notifications.notification_text_models import (
    NotificationTextPlain,
    NotificationTextTemplate,
)

__all__ = (
    "NotificationLink",
    "NotificationRecord",
    "NotificationsListCursor",
    "NotificationsListPage",
    "NotificationsListRequest",
    "NotificationsListResponse",
    "NotificationsMarkReadRequest",
)


class NotificationLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_type: NotificationLinkType
    value: str = Field(..., min_length=1)


class NotificationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    user_id: int = Field(..., ge=1)
    created_at_ms: int = Field(..., ge=1)
    type: NotificationType
    title: Annotated[
        NotificationTextPlain | NotificationTextTemplate,
        Field(discriminator="text_type"),
    ]
    message: Annotated[
        NotificationTextPlain | NotificationTextTemplate,
        Field(discriminator="text_type"),
    ]
    source: str | None = Field(default=None, min_length=1)
    link: NotificationLink | None = None
    read_at_ms: int | None = Field(default=None, ge=1)


class NotificationsListCursor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at_ms: int = Field(..., ge=1)
    id: str = Field(..., min_length=1)


class NotificationsListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(..., ge=1, le=500)
    before_created_at_ms: int | None = Field(default=None, ge=1)
    before_id: str | None = Field(default=None, min_length=1)
    unread_only: bool = False

    @model_validator(mode="after")
    def validate_cursor(self) -> NotificationsListRequest:
        has_created_at = self.before_created_at_ms is not None
        has_id = self.before_id is not None
        if has_created_at != has_id:
            raise ValueError(
                "Notification cursor requires both before_created_at_ms and before_id.",
            )
        return self


class NotificationsListPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notifications: list[NotificationRecord] = Field(default_factory=list[NotificationRecord])
    next_cursor: NotificationsListCursor | None = None


class NotificationsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notifications: list[NotificationRecord] = Field(default_factory=list[NotificationRecord])
    total_count: int = Field(..., ge=0)
    unread_count: int = Field(..., ge=0)
    next_cursor: NotificationsListCursor | None = None

    @model_validator(mode="after")
    def validate_counts(self) -> NotificationsListResponse:
        if self.unread_count > self.total_count:
            raise ValueError("Notification unread_count cannot exceed total_count.")
        return self


class NotificationsMarkReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification_ids: list[str] = Field(..., min_length=1)
