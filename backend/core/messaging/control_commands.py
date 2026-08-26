"""SoAI - Messaging control command grammar [backend/core/messaging/control_commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.messaging.ingress_models import NormalizedMessagingEvent

__all__ = ("classify_messaging_control_command",)

if TYPE_CHECKING:
    from typing import Literal

    type MessagingControlCommand = Literal["help", "status", "cancel", "new"]


def _resolve_control_command(text: str) -> MessagingControlCommand | None:
    if text == "/help":
        return "help"
    if text == "/status":
        return "status"
    if text == "/cancel":
        return "cancel"
    if text == "/new":
        return "new"
    return None


def classify_messaging_control_command(
    event: NormalizedMessagingEvent,
    *,
    verified_principal_label: str | None,
) -> MessagingControlCommand | None:
    if event.classification != "prompt" or event.media:
        return None
    text = event.text.strip()
    if event.platform != "telegram":
        return _resolve_control_command(text)
    command_text, separator, target = text.partition("@")
    if event.remote_thread_type == "group":
        expected = (verified_principal_label or "").strip().removeprefix("@").lower()
        if separator != "@" or not expected or target.lower() != expected:
            return None
        return _resolve_control_command(command_text)
    if separator != "@":
        return _resolve_control_command(command_text)
    expected = (verified_principal_label or "").strip().removeprefix("@").lower()
    if not expected or target.lower() != expected:
        return None
    return _resolve_control_command(command_text)
