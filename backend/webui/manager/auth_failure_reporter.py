"""SoAI - WebUI auth failure reporter composition for guards and logs [backend/webui/manager/auth_failure_reporter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.auth.auth_decisions import AuthenticationDecision
from core.runtime.protocols import RequestProtocol
from core.wallpaper.protocols import AuthGuardProtocol
from webui.manager.auth_guard_failure_handling import (
    register_failure_and_build_decision,
)
from webui.manager.internal_protocols import AuthFailureLoggerProtocol

__all__ = ("AuthFailureReporter",)


@dataclass(frozen=True, slots=True)
class AuthFailureReporter:
    request: RequestProtocol
    guard: AuthGuardProtocol
    log_failure: AuthFailureLoggerProtocol
    trace_id: str | None
    auth_method: str
    client_ip: str

    async def report_failure(
        self,
        message: str,
        reason: str,
        *,
        bucket_identifiers: tuple[str, ...],
        fingerprint: str | None = None,
        failure_category: str | None = None,
    ) -> AuthenticationDecision:
        return await register_failure_and_build_decision(
            request=self.request,
            guard=self.guard,
            log_failure=self.log_failure,
            trace_id=self.trace_id,
            auth_method=self.auth_method,
            message=message,
            reason=reason,
            client_ip=self.client_ip,
            bucket_identifiers=bucket_identifiers,
            fingerprint=fingerprint,
            failure_category=failure_category,
        )
