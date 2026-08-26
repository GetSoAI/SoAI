"""SoAI - WebUI notification text schema models [backend/core/notifications/notification_text_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from core.notifications.notification_contracts import (
    NotificationTemplateId,
    resolve_notification_template_required_params,
)
from core.serialization.json import serialize_json_compact_stable

__all__ = (
    "NotificationTextPlain",
    "NotificationTextTemplate",
    "notification_text_from_plain",
    "notification_text_from_template",
    "parse_notification_text_db",
    "serialize_notification_text_db",
)


class NotificationTextPlain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text_type: Literal["text"]
    text: str = Field(..., min_length=1)


class NotificationTextTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text_type: Literal["template"]
    template: NotificationTemplateId
    params: dict[str, str] = Field(default_factory=dict[str, str])

    @model_validator(mode="after")
    def validate_params(self) -> NotificationTextTemplate:
        if not isinstance(self.params, dict):
            raise ValueError("Notification payload is invalid.")
        normalized_params: dict[str, str] = {}
        for key, raw_value in self.params.items():
            if not isinstance(key, str):
                raise ValueError("Notification payload is invalid.")
            normalized_key = key.strip()
            if not normalized_key:
                raise ValueError("Notification payload is invalid.")
            if normalized_key in normalized_params:
                raise ValueError("Notification payload is invalid.")
            if not isinstance(raw_value, str):
                raise ValueError("Notification payload is invalid.")
            normalized_value = raw_value.strip()
            if not normalized_value:
                raise ValueError("Notification payload is invalid.")
            normalized_params[normalized_key] = normalized_value
        required_keys = resolve_notification_template_required_params(self.template)
        if set(normalized_params.keys()) != set(required_keys):
            raise ValueError("Notification payload is invalid.")
        self.params = normalized_params
        return self


def _notification_text_adapter() -> TypeAdapter[NotificationTextPlain | NotificationTextTemplate]:
    return TypeAdapter(
        Annotated[
            NotificationTextPlain | NotificationTextTemplate,
            Field(discriminator="text_type"),
        ],
    )


def notification_text_from_plain(value: str) -> NotificationTextPlain:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Notification text must not be empty.")
    return NotificationTextPlain(text_type="text", text=normalized)


def notification_text_from_template(
    template: NotificationTemplateId,
    params: dict[str, str] | None = None,
) -> NotificationTextTemplate:
    resolved_params = params or {}
    return NotificationTextTemplate(
        text_type="template",
        template=template,
        params=resolved_params,
    )


def parse_notification_text_db(value: str) -> NotificationTextPlain | NotificationTextTemplate:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Notification payload is invalid.")
    try:
        parsed = _notification_text_adapter().validate_json(normalized)
    except ValidationError as exception:
        raise ValueError("Notification payload is invalid.") from exception
    if isinstance(parsed, NotificationTextPlain):
        trimmed_text = parsed.text.strip()
        if not trimmed_text:
            raise ValueError("Notification payload is invalid.")
        if trimmed_text != parsed.text:
            return NotificationTextPlain(text_type="text", text=trimmed_text)
        return parsed
    return parsed


def serialize_notification_text_db(value: NotificationTextPlain | NotificationTextTemplate) -> str:
    return serialize_json_compact_stable(value.model_dump(mode="json"))
