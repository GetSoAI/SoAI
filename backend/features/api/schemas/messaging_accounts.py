"""SoAI - Messaging account V1 API schemas [backend/features/api/schemas/messaging_accounts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, model_validator

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from features.api.schemas.json_fields import PydanticJSONValue

if TYPE_CHECKING:
    type MessagingCredentialsRequest = (
        TelegramMessagingCredentials | DiscordMessagingCredentials | WhatsAppMessagingCredentials
    )

__all__ = (
    "DiscordMessagingCredentials",
    "MessagingAccountCreateRequest",
    "MessagingAccountDeleteRequest",
    "MessagingAccountLifecycleRequest",
    "MessagingAccountUpdateRequest",
    "MessagingAuthorizedSenderRequest",
    "TelegramMessagingCredentials",
    "WhatsAppMessagingCredentials",
    "validate_messaging_credentials_platform",
)


class TelegramMessagingCredentials(SoAIV1StrictModel):
    bot_token: StrictStr = Field(..., min_length=1, max_length=512)
    webhook_secret: StrictStr = Field(
        ...,
        min_length=16,
        max_length=256,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class DiscordMessagingCredentials(SoAIV1StrictModel):
    bot_token: StrictStr = Field(..., min_length=1, max_length=512)
    application_id: StrictStr = Field(..., min_length=1, max_length=255)


class WhatsAppMessagingCredentials(SoAIV1StrictModel):
    access_token: StrictStr = Field(..., min_length=1, max_length=2048)
    phone_number_id: StrictStr = Field(..., min_length=1, max_length=255)
    business_account_id: StrictStr = Field(..., min_length=1, max_length=255)
    application_id: StrictStr = Field(..., min_length=1, max_length=255)
    api_version: StrictStr = Field(..., pattern=r"^v[1-9][0-9]*\.[0-9]+$")
    app_secret: StrictStr = Field(..., min_length=1, max_length=512)
    verify_token: StrictStr = Field(..., min_length=16, max_length=256)


class MessagingAuthorizedSenderRequest(SoAIV1StrictModel):
    sender_id: StrictStr = Field(..., min_length=1, max_length=255)
    display_label: StrictStr | None = Field(default=None, max_length=255)


class MessagingAccountCreateRequest(SoAIV1StrictModel):
    platform: Literal["telegram", "whatsapp", "discord"]
    label: StrictStr = Field(..., min_length=1, max_length=120)
    credentials: (
        TelegramMessagingCredentials | DiscordMessagingCredentials | WhatsAppMessagingCredentials
    )
    model_settings: dict[str, PydanticJSONValue]
    locale: Literal["en", "it"]
    plaintext_secret_replies_enabled: StrictBool
    accept_messages_from_anyone: StrictBool
    authorized_senders: list[MessagingAuthorizedSenderRequest]
    replace_existing_callback: StrictBool

    @model_validator(mode="after")
    def validate_credentials_match_platform(self) -> MessagingAccountCreateRequest:
        validate_messaging_credentials_platform(self.platform, self.credentials)
        return self


class MessagingAccountUpdateRequest(SoAIV1StrictModel):
    expected_revision: StrictInt = Field(..., ge=1)
    label: StrictStr = Field(..., min_length=1, max_length=120)
    credentials: (
        TelegramMessagingCredentials
        | DiscordMessagingCredentials
        | WhatsAppMessagingCredentials
        | None
    ) = None
    model_settings: dict[str, PydanticJSONValue]
    locale: Literal["en", "it"]
    enabled: StrictBool
    plaintext_secret_replies_enabled: StrictBool
    accept_messages_from_anyone: StrictBool
    authorized_senders: list[MessagingAuthorizedSenderRequest]
    replace_existing_callback: StrictBool


class MessagingAccountDeleteRequest(SoAIV1StrictModel):
    expected_revision: StrictInt = Field(..., ge=1)


class MessagingAccountLifecycleRequest(SoAIV1StrictModel):
    expected_revision: StrictInt = Field(..., ge=1)
    enabled: StrictBool
    replace_existing_callback: StrictBool = False


def validate_messaging_credentials_platform(
    platform: Literal["telegram", "whatsapp", "discord"],
    credentials: (
        TelegramMessagingCredentials | DiscordMessagingCredentials | WhatsAppMessagingCredentials
    ),
) -> None:
    if platform == "telegram" and isinstance(credentials, TelegramMessagingCredentials):
        return
    if platform == "whatsapp" and isinstance(credentials, WhatsAppMessagingCredentials):
        return
    if platform == "discord" and isinstance(credentials, DiscordMessagingCredentials):
        return
    raise ValidationError("Messaging credentials do not match the selected platform.")
