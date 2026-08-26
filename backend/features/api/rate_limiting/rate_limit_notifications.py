"""SoAI - API rate limit notification emission [backend/features/api/rate_limiting/rate_limit_notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.notifications.system_admin_alerts import create_api_rate_limit_admin_alert
from features.api.rate_limiting.rate_limit_evaluator import RateLimitBreach

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol

__all__ = ("notify_rate_limit_breach_noncritical",)


async def notify_rate_limit_breach_noncritical(
    *,
    database_notifications: DatabaseNotificationsProtocol,
    breach: RateLimitBreach,
    log: LoggerProtocol,
    operation: str,
) -> None:
    try:
        await create_api_rate_limit_admin_alert(
            database_notifications,
            client_key=breach.client_key,
            scope_key=breach.scope_key,
            rule_label=breach.rule.label,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            log,
            exception,
            message="Failed to create API rate limit notification.",
            operation=operation,
            details={"scope_key": breach.scope_key, "rule_label": breach.rule.label},
            level="warning",
        )
