"""SoAI - Administrator device-session hardening findings [backend/core/security/admin_session_hardening.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.security.hardening_types import SecurityHardeningIssue
from core.validation.strict_numbers import require_non_negative_int_strict

if TYPE_CHECKING:
    from core.auth.protocols_database_tokens import DatabaseTokensProtocol

__all__ = (
    "ADMIN_SESSION_DEVICE_WARNING_THRESHOLD",
    "build_admin_session_hardening_issues",
    "collect_admin_session_hardening_issues",
)

ADMIN_SESSION_DEVICE_WARNING_THRESHOLD = 10
LOGGER_NAME = "SoAI.core.security.admin_session_hardening"
OPERATION_COLLECT_ADMIN_SESSION_HARDENING = "admin_session_hardening.collect"


def build_admin_session_hardening_issues(
    active_device_count: int,
) -> tuple[SecurityHardeningIssue, ...]:
    validated_count = require_non_negative_int_strict(
        active_device_count,
        error_message="Active administrator session device count must be non-negative.",
    )
    if validated_count <= ADMIN_SESSION_DEVICE_WARNING_THRESHOLD:
        return ()
    return (
        SecurityHardeningIssue(
            issue_id="excessive_active_admin_session_devices",
            message=(
                f"{validated_count} devices currently have active administrator sessions, "
                f"which is more than {ADMIN_SESSION_DEVICE_WARNING_THRESHOLD}. Each active "
                "administrator device increases the privileged access surface. Review the "
                "active devices in Users settings and revoke sessions that are no longer needed."
            ),
            config_keys=(),
        ),
    )


def _admin_session_hardening_check_failed_issue() -> SecurityHardeningIssue:
    return SecurityHardeningIssue(
        issue_id="admin_session_device_hardening_check_failed",
        message=(
            "Administrator device-session hardening checks could not read the active session "
            "registry. Review backend logs before exposing SoAI."
        ),
        config_keys=(),
    )


async def collect_admin_session_hardening_issues(
    database_tokens: DatabaseTokensProtocol,
) -> tuple[SecurityHardeningIssue, ...]:
    try:
        active_device_count = await database_tokens.count_active_admin_session_devices()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to collect administrator device-session hardening snapshot.",
            operation=OPERATION_COLLECT_ADMIN_SESSION_HARDENING,
            level="warning",
        )
        return (_admin_session_hardening_check_failed_issue(),)
    return build_admin_session_hardening_issues(active_device_count)
