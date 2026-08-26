"""SoAI - Messaging callback ownership diagnostics [backend/features/messaging/callback_observability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.messaging.observability_emission import log_messaging_diagnostic
from core.messaging.observability_fields import MessagingLogFields

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.messaging.callback_contracts import (
        MessagingCallbackInspection,
        MessagingCallbackMutation,
    )

__all__ = (
    "log_messaging_callback_inspection",
    "log_messaging_callback_mutation",
)

LOGGER_NAME = "SoAI.features.messaging.callback_observability"


def log_messaging_callback_inspection(
    *,
    operation: str,
    platform: MessagingPlatform,
    account_id: str,
    inspection: MessagingCallbackInspection,
    page_count: int | None = None,
) -> None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging callback ownership inspected.",
        log_fields=MessagingLogFields(
            operation=operation,
            platform=platform,
            phase="progress",
            outcome="success",
            account_id=account_id,
            ownership_state=inspection.state,
            page_count=page_count,
        ),
    )


def log_messaging_callback_mutation(
    *,
    operation: str,
    platform: MessagingPlatform,
    account_id: str,
    mutation: MessagingCallbackMutation,
) -> None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging callback ownership mutated.",
        log_fields=MessagingLogFields(
            operation=operation,
            platform=platform,
            phase="complete",
            outcome="success",
            account_id=account_id,
            ownership_state=mutation.ownership_state,
        ),
    )
