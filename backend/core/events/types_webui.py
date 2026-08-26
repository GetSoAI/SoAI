"""SoAI - WebUI event types [backend/core/events/types_webui.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.events.types_base import Event
from core.types.json import JSONDict, JSONValue

__all__ = (
    "AutomationCreatedEvent",
    "AutomationDeletedEvent",
    "AutomationRunCreatedEvent",
    "AutomationRunUpdatedEvent",
    "AutomationUpdatedEvent",
    "LicensingStatusChangedEvent",
    "NotificationCreatedEvent",
    "NotificationDeletedEvent",
    "NotificationsClearedEvent",
    "NotificationsMarkedReadEvent",
    "PromptListUpdatedEvent",
    "UserCreatedEvent",
    "UserDeletedEvent",
    "UserPasswordChangedEvent",
    "UserRoleChangedEvent",
    "UserSessionInvalidatedEvent",
    "UserUsernameChangedEvent",
    "WallpaperChangedEvent",
)


@dataclass(slots=True)
class PromptListUpdatedEvent(Event):
    user_id: int = 0
    color: str | None = None
    prompts: list[JSONDict] = field(default_factory=list[JSONDict])


@dataclass(slots=True)
class AutomationCreatedEvent(Event):
    user_id: int
    automation_id: str


@dataclass(slots=True)
class AutomationUpdatedEvent(Event):
    user_id: int
    automation_id: str


@dataclass(slots=True)
class AutomationDeletedEvent(Event):
    user_id: int
    automation_id: str


@dataclass(slots=True)
class AutomationRunCreatedEvent(Event):
    user_id: int
    automation_id: str
    run_id: str


@dataclass(slots=True)
class AutomationRunUpdatedEvent(Event):
    user_id: int
    automation_id: str
    run_id: str


@dataclass(slots=True)
class LicensingStatusChangedEvent(Event): ...


@dataclass(slots=True)
class NotificationCreatedEvent(Event):
    user_id: int
    notification_id: str
    notification_type: str
    title: JSONValue
    message: JSONValue
    created_at_ms: int
    source: str | None = None
    link: JSONValue | None = None


@dataclass(slots=True)
class NotificationDeletedEvent(Event):
    user_id: int
    notification_id: str


@dataclass(slots=True)
class NotificationsClearedEvent(Event):
    user_id: int


@dataclass(slots=True)
class NotificationsMarkedReadEvent(Event):
    user_id: int
    notification_ids: list[str]


@dataclass(slots=True)
class UserCreatedEvent(Event):
    user_id: int
    username: str
    is_admin: bool
    identity_revision: int


@dataclass(slots=True)
class UserDeletedEvent(Event):
    user_id: int
    username: str


@dataclass(slots=True)
class UserPasswordChangedEvent(Event):
    operation_id: str
    actor_user_id: int
    user_id: int
    username: str
    revoked_session_jtis: tuple[str, ...]
    rotation_source_jti: str | None
    password_revision: int


@dataclass(slots=True)
class UserRoleChangedEvent(Event):
    user_id: int
    username: str
    is_admin: bool
    identity_revision: int


@dataclass(slots=True)
class UserUsernameChangedEvent(Event):
    operation_id: str
    actor_user_id: int
    user_id: int
    previous_username: str
    username: str
    identity_revision: int
    revoked_session_jtis: tuple[str, ...]
    rotation_source_jti: str | None


@dataclass(slots=True)
class UserSessionInvalidatedEvent(Event):
    user_id: int
    username: str
    reason: str
    session_jtis: tuple[str, ...] | None = None


@dataclass(slots=True)
class WallpaperChangedEvent(Event): ...
