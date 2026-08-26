"""SoAI - Non-critical identity mutation audit acceleration [backend/features/api/routes/webui/identity_mutation_audit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from features.api.runtime.audit import log_audit_event

LOGGER_NAME = "SoAI.features.api.identity_mutation_audit"
OPERATION = "webui.identity_mutation.audit"


def log_identity_mutation_audit_noncritical(
    request: Request,
    *,
    action: str,
    actor_user_id: int,
    target_user_id: int,
    target_username: str,
    previous_username: str | None = None,
) -> None:
    details: dict[str, int | str] = {
        "actor_user_id": actor_user_id,
        "target_user_id": target_user_id,
    }
    if previous_username is not None:
        details["previous_username"] = previous_username
    try:
        log_audit_event(
            request,
            action,
            f"user:{target_username}",
            details,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Durable identity mutation committed but audit acceleration failed.",
            operation=OPERATION,
            details={
                "action": action,
                "actor_user_id": actor_user_id,
                "target_user_id": target_user_id,
            },
            level="warning",
        )


__all__ = ("log_identity_mutation_audit_noncritical",)
