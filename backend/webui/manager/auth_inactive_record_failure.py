"""SoAI - WebUI auth failure handling for inactive stored tokens [backend/webui/manager/auth_inactive_record_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.auth.auth_decisions import AuthenticationDecision
from core.validation.boolean_coercion import coerce_bool_flag
from core.validation.coercion import coerce_int_from_scalar
from webui.manager.auth_failure_reporter import AuthFailureReporter

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict

__all__ = ("report_inactive_record_auth_failure",)


async def report_inactive_record_auth_failure(
    *,
    failure_reporter: AuthFailureReporter,
    inactive_record: JSONDict | None,
    fingerprint: str,
    now_ms: int,
    logger: TraceLogger,
    coerce_bool_operation: str,
    bucket_identifiers: tuple[str, ...],
    use_reason_as_failure_category: bool,
) -> AuthenticationDecision:
    inactive_revoked = coerce_bool_flag(
        inactive_record.get("revoked") if inactive_record else None,
        logger=logger,
        operation=coerce_bool_operation,
        default=False,
    )
    expires_at_ms = (
        coerce_int_from_scalar(inactive_record.get("expires_at_ms")) if inactive_record else None
    )
    if inactive_record and inactive_revoked:
        reason = "revoked"
    elif inactive_record and expires_at_ms is not None and (expires_at_ms <= int(now_ms)):
        reason = "expired"
    else:
        reason = "unknown"
    return await failure_reporter.report_failure(
        "You are not authenticated.",
        reason,
        bucket_identifiers=bucket_identifiers,
        fingerprint=fingerprint[:12],
        failure_category=reason if use_reason_as_failure_category else None,
    )
