"""SoAI - Messaging account persistence inputs [backend/core/messaging/account_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.types.json import JSONDict

if TYPE_CHECKING:
    from typing import Literal

    from core.conversations.conversation_source import MessagingPlatform

    type MessagingAccountLifecycleState = Literal[
        "enabled",
        "disabled",
        "deleting",
        "degraded",
    ]
    type MessagingAccountLocale = Literal["en", "it"]

__all__ = (
    "MessagingAccountCreate",
    "MessagingAccountFence",
    "MessagingAccountReconciliationResult",
    "MessagingAccountUpdate",
    "MessagingAccountDeleteFence",
    "MessagingActiveInputIdentity",
    "MessagingAuthorizedSender",
    "MessagingConversationVersion",
    "MessagingProgressTarget",
    "ResolvedMessagingPrincipal",
)


@dataclass(frozen=True, slots=True)
class MessagingAccountFence:
    user_id: int
    account_id: str
    platform: MessagingPlatform
    revision: int
    lifecycle_generation: int


@dataclass(frozen=True, slots=True)
class MessagingAccountReconciliationResult:
    before: JSONDict
    after: JSONDict
    notification_created: bool


@dataclass(frozen=True, slots=True)
class MessagingAuthorizedSender:
    sender_id: str
    display_label: str | None


@dataclass(frozen=True, slots=True)
class ResolvedMessagingPrincipal:
    platform: MessagingPlatform
    principal_id: str
    principal_label: str | None
    parent_principal_id: str | None
    application_principal_id: str | None


@dataclass(frozen=True, slots=True)
class MessagingAccountCreate:
    account_id: str
    platform: MessagingPlatform
    label: str
    principal_id: str
    principal_label: str | None
    parent_principal_id: str | None
    application_principal_id: str | None
    credentials: JSONDict
    model_settings: JSONDict
    locale: MessagingAccountLocale
    lifecycle_state: MessagingAccountLifecycleState
    plaintext_secret_replies_enabled: bool
    accept_messages_from_anyone: bool
    authorized_senders: tuple[MessagingAuthorizedSender, ...]


@dataclass(frozen=True, slots=True)
class MessagingAccountUpdate:
    label: str
    principal_label: str | None
    parent_principal_id: str | None
    application_principal_id: str | None
    credentials: JSONDict | None
    model_settings: JSONDict
    locale: MessagingAccountLocale
    lifecycle_state: MessagingAccountLifecycleState
    plaintext_secret_replies_enabled: bool
    accept_messages_from_anyone: bool
    authorized_senders: tuple[MessagingAuthorizedSender, ...]


@dataclass(frozen=True, slots=True)
class MessagingActiveInputIdentity:
    input_id: str
    conv_id: str
    user_id: int
    task_id: str | None


@dataclass(frozen=True, slots=True)
class MessagingAccountDeleteFence:
    account: JSONDict
    task_ids: tuple[str, ...]
    active_inputs: tuple[MessagingActiveInputIdentity, ...]


@dataclass(frozen=True, slots=True)
class MessagingConversationVersion:
    conv_id: str
    last_modified_at_ms: int


@dataclass(frozen=True, slots=True)
class MessagingProgressTarget:
    input_id: str
    account_id: str
    user_id: int
    platform: MessagingPlatform
    remote_thread_key: str
    credentials: JSONDict
