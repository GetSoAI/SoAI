"""SoAI - Messaging account lifecycle transition reporting [backend/features/messaging/account_transition_reporting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.messaging.callback_contracts import (
    require_messaging_callback_ownership_state,
)
from core.messaging.observability_emission import (
    log_messaging_diagnostic,
    log_messaging_lifecycle,
)
from core.messaging.observability_fields import MessagingLogFields
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.messaging.callback_contracts import MessagingCallbackOwnershipState
    from core.types.json import JSONDict

__all__ = (
    "read_messaging_ownership_state",
    "report_messaging_account_transition",
)

LOGGER_NAME = "SoAI.features.messaging.account_transition_reporting"


def read_messaging_ownership_state(
    account: JSONDict,
) -> MessagingCallbackOwnershipState:
    value = account.get("callback_ownership_state")
    return require_messaging_callback_ownership_state(
        value if isinstance(value, str) else None,
    )


def _is_healthy(account: JSONDict) -> bool:
    return account.get("lifecycle_state") == "enabled"


def _optional_int(account: JSONDict, key: str) -> int | None:
    value = account.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _account_fields(
    *,
    operation: str,
    platform: MessagingPlatform,
    account_id: str,
    account: JSONDict,
) -> MessagingLogFields:
    return MessagingLogFields(
        operation=operation,
        platform=platform,
        phase="complete",
        account_id=account_id,
        revision=_optional_int(account, "revision"),
        lifecycle_generation=_optional_int(account, "lifecycle_generation"),
        ownership_state=read_messaging_ownership_state(account),
        health_code=coerce_optional_trimmed_str(account.get("health_code")),
    )


def _report_health_edge(
    log_fields: MessagingLogFields,
    *,
    before: JSONDict,
    after: JSONDict,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    was_healthy = _is_healthy(before)
    is_healthy = _is_healthy(after)
    if was_healthy and not is_healthy:
        log_messaging_lifecycle(
            logger,
            message="Messaging account runtime became degraded.",
            log_fields=replace(log_fields, outcome="failure"),
        )
        return True
    if is_healthy and not was_healthy:
        log_messaging_lifecycle(
            logger,
            message="Messaging account runtime recovered.",
            log_fields=replace(log_fields, outcome="success"),
        )
        return True
    return False


def _report_ownership_edge(
    log_fields: MessagingLogFields,
    *,
    before: JSONDict,
    after: JSONDict,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    previous_state = read_messaging_ownership_state(before)
    current_state = read_messaging_ownership_state(after)
    if previous_state == current_state:
        return False
    if current_state == "owned":
        log_messaging_lifecycle(
            logger,
            message=(
                "Messaging callback ownership installed."
                if previous_state in ("unknown", "not_applicable")
                else "Messaging callback ownership repaired."
            ),
            log_fields=replace(log_fields, outcome="success"),
        )
        return True
    if previous_state == "owned" and current_state == "unknown":
        log_messaging_lifecycle(
            logger,
            message="Messaging callback ownership safely removed.",
            log_fields=replace(log_fields, outcome="success"),
        )
        return True
    log_messaging_diagnostic(
        logger,
        message="Messaging callback ownership changed.",
        log_fields=replace(log_fields, outcome="unknown"),
    )
    return True


def report_messaging_account_transition(
    *,
    operation: str,
    platform: MessagingPlatform,
    account_id: str,
    before: JSONDict,
    after: JSONDict | None,
) -> None:
    if after is None:
        log_messaging_diagnostic(
            get_logger(LOGGER_NAME),
            message="Messaging account reconciliation was superseded.",
            log_fields=replace(
                _account_fields(
                    operation=operation,
                    platform=platform,
                    account_id=account_id,
                    account=before,
                ),
                outcome="superseded",
            ),
        )
        return
    log_fields = _account_fields(
        operation=operation,
        platform=platform,
        account_id=account_id,
        account=after,
    )
    health_changed = _report_health_edge(log_fields, before=before, after=after)
    ownership_changed = _report_ownership_edge(log_fields, before=before, after=after)
    if health_changed or ownership_changed:
        return
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging account state unchanged after reconciliation.",
        log_fields=replace(log_fields, outcome="success"),
    )
