"""SoAI - WebUI session identity and registration contracts [backend/core/auth/webui_sessions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from core.errors.exceptions import ConflictError, ValidationError
from core.serialization.base64_values import decode_base64_ascii_urlsafe
from core.serialization.json_parsing import parse_json_dict
from core.validation.strings import require_bounded_trimmed_text

__all__ = (
    "ANDROID_DEVICE_COOKIE_NAME",
    "WEBUI_DEVICE_LABEL_MAX_LENGTH",
    "WebuiSessionDescriptor",
    "WebuiSessionJtiCollisionError",
    "WebuiSessionRegistrationResult",
    "WebuiSessionReplacement",
    "build_webui_session_descriptor",
    "require_webui_session_client_type",
)

ANDROID_DEVICE_COOKIE_NAME = "soai-android-device"
WEBUI_SESSION_TOUCH_INTERVAL_MS = 300_000
_DEVICE_COOKIE_MAX_LENGTH = 2_048
WEBUI_DEVICE_LABEL_MAX_LENGTH = 80
_USER_AGENT_MAX_LENGTH = 512


@dataclass(frozen=True, slots=True)
class WebuiSessionDescriptor:
    client_type: Literal["web", "android"]
    device_id: str | None
    device_label: str
    user_agent: str


@dataclass(frozen=True, slots=True)
class WebuiSessionRegistrationResult:
    jti: str
    user_id: int
    revoked_jtis: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WebuiSessionReplacement:
    jti: str
    source_jti: str
    issued_at_ms: int
    expires_at_ms: int


class WebuiSessionJtiCollisionError(ConflictError): ...


def require_webui_session_client_type(value: str) -> Literal["web", "android"]:
    if value == "web":
        return "web"
    if value == "android":
        return "android"
    raise ValidationError("WebUI session client type is invalid.")


def _decode_android_device_cookie(value: str) -> dict[str, str]:
    normalized = value.strip()
    if not normalized or len(normalized) > _DEVICE_COOKIE_MAX_LENGTH:
        raise ValidationError("Android device metadata is invalid.")
    padding = "=" * (-len(normalized) % 4)
    decoded = decode_base64_ascii_urlsafe(
        normalized + padding,
        error_message="Android device metadata is invalid.",
    )
    payload = parse_json_dict(decoded, field="Android device metadata")
    if set(payload) != {"device_id", "device_label"}:
        raise ValidationError("Android device metadata fields are invalid.")
    device_id = payload.get("device_id")
    device_label = payload.get("device_label")
    if not isinstance(device_id, str) or not isinstance(device_label, str):
        raise ValidationError("Android device metadata fields are invalid.")
    return {"device_id": device_id, "device_label": device_label}


def build_webui_session_descriptor(
    *,
    android_cookie: str | None,
    user_agent: str | None,
) -> WebuiSessionDescriptor:
    normalized_user_agent = (user_agent or "").strip()[:_USER_AGENT_MAX_LENGTH]
    if android_cookie is None:
        return WebuiSessionDescriptor(
            client_type="web",
            device_id=None,
            device_label="Web browser",
            user_agent=normalized_user_agent,
        )
    payload = _decode_android_device_cookie(android_cookie)
    raw_device_id = payload["device_id"].strip()
    try:
        device_id = str(uuid.UUID(raw_device_id))
    except ValueError as exception:
        raise ValidationError("Android device id must be a UUID.") from exception
    device_label = require_bounded_trimmed_text(
        payload["device_label"],
        type_message="Android device label must be a string.",
        empty_message="Android device label must not be empty.",
        max_length=WEBUI_DEVICE_LABEL_MAX_LENGTH,
        max_length_message="Android device label must be 80 characters or fewer.",
    )
    return WebuiSessionDescriptor(
        client_type="android",
        device_id=device_id,
        device_label=device_label,
        user_agent=normalized_user_agent,
    )
