"""SoAI - Messaging callback ownership contracts [backend/core/messaging/callback_contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ConflictError, ValidationError
from core.messaging.callback_urls import fingerprint_messaging_callback_url

if TYPE_CHECKING:
    type MessagingCallbackOwnershipState = Literal[
        "unknown",
        "owned",
        "external",
        "lost",
        "not_applicable",
    ]

__all__ = (
    "MessagingCallbackInspection",
    "MessagingCallbackMutation",
    "require_messaging_callback_ownership_state",
    "resolve_callback_install_precondition",
    "resolve_callback_removal_precondition",
)


@dataclass(frozen=True, slots=True)
class MessagingCallbackInspection:
    current_url: str | None
    desired_url: str
    state: Literal["vacant", "owned", "external"]


@dataclass(frozen=True, slots=True)
class MessagingCallbackMutation:
    callback_fingerprint: str | None
    ownership_state: MessagingCallbackOwnershipState


def require_messaging_callback_ownership_state(
    value: str | None,
) -> MessagingCallbackOwnershipState:
    if value == "unknown":
        return "unknown"
    if value == "owned":
        return "owned"
    if value == "external":
        return "external"
    if value == "lost":
        return "lost"
    if value == "not_applicable":
        return "not_applicable"
    raise ValidationError("Messaging callback ownership state is invalid.")


def resolve_callback_install_precondition(
    inspection: MessagingCallbackInspection,
    *,
    replace_existing_callback: bool,
    refresh_owned_callback: bool,
) -> MessagingCallbackMutation | None:
    if inspection.state == "external" and not replace_existing_callback:
        raise ConflictError(
            "The provider callback changed before installation. Explicit replacement confirmation is required.",
            details={"callback_ownership_state": "external"},
        )
    if inspection.state == "owned" and not refresh_owned_callback:
        return MessagingCallbackMutation(
            callback_fingerprint=fingerprint_messaging_callback_url(
                inspection.desired_url,
            ),
            ownership_state="owned",
        )
    return None


def resolve_callback_removal_precondition(
    inspection: MessagingCallbackInspection,
    *,
    installed_callback_fingerprint: str | None,
) -> MessagingCallbackMutation | None:
    current_url = inspection.current_url
    if current_url is None:
        return MessagingCallbackMutation(callback_fingerprint=None, ownership_state="unknown")
    current_fingerprint = fingerprint_messaging_callback_url(current_url)
    if (
        installed_callback_fingerprint is None
        or current_fingerprint != installed_callback_fingerprint
    ):
        return MessagingCallbackMutation(callback_fingerprint=None, ownership_state="lost")
    return None
