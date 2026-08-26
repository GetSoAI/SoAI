"""SoAI - Messaging webhook rate control and durable admission [backend/features/api/routes/messaging/webhook_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.rate_limiting.definitions import RateLimitRule
from core.rate_limiting.moving_window import MovingWindowRateLimiter
from core.timing.epoch import epoch_seconds_float
from features.api.routes.messaging.webhook_observability import (
    MessagingWebhookTrace,
    log_messaging_webhook_admission,
    log_messaging_webhook_complete,
    log_messaging_webhook_rate,
)
from features.api.runtime.errors import raise_invalid_request, raise_rate_limit

if TYPE_CHECKING:
    from core.messaging.ingress_models import NormalizedMessagingEvent
    from features.api.runtime.context import ApiContext

__all__ = ("dispatch_authenticated_events", "enforce_authenticated_account_rate")

MESSAGING_WEBHOOK_MAX_EVENTS = 100


def _account_rate_rules() -> tuple[RateLimitRule, ...]:
    return (
        RateLimitRule(amount=30, window_seconds=10, label="Messaging account burst"),
        RateLimitRule(amount=120, window_seconds=60, label="Messaging account sustained"),
    )


def _sender_rate_rules() -> tuple[RateLimitRule, ...]:
    return (
        RateLimitRule(amount=20, window_seconds=10, label="Messaging sender burst"),
        RateLimitRule(amount=60, window_seconds=60, label="Messaging sender sustained"),
    )


def _request_limiter(request: Request) -> MovingWindowRateLimiter:
    try:
        limiter = request.app.state.request_rate_limiter
    except AttributeError as exception:
        raise ValidationError("Messaging webhook rate limiter is unavailable.") from exception
    if not isinstance(limiter, MovingWindowRateLimiter):
        raise ValidationError("Messaging webhook rate limiter is invalid.")
    return limiter


def _enforce_authenticated_rate(
    request: Request,
    *,
    rules: tuple[RateLimitRule, ...],
    client_key: str,
    scope_key: str,
    trace: MessagingWebhookTrace,
    classification: str | None = None,
) -> None:
    decision = _request_limiter(request).hit(
        rules=rules,
        client_key=client_key,
        scope_key=scope_key,
    )
    if decision.allowed:
        log_messaging_webhook_rate(
            trace,
            accepted=True,
            classification=classification,
        )
        return
    stats = decision.stats
    if stats is None:
        raise ValidationError("Messaging webhook rate limiter returned an invalid decision.")
    retry_after_seconds = max(
        1,
        math.ceil(stats.reset_epoch_seconds - epoch_seconds_float()),
    )
    log_messaging_webhook_rate(
        trace,
        accepted=False,
        classification=classification,
        retry_after_ms=retry_after_seconds * 1000,
    )
    raise_rate_limit(
        request,
        "Messaging webhook rate limit exceeded.",
        headers={"Retry-After": str(retry_after_seconds)},
    )


def enforce_authenticated_account_rate(
    request: Request,
    *,
    account_id: str,
    platform: str,
    trace: MessagingWebhookTrace,
) -> None:
    _enforce_authenticated_rate(
        request,
        rules=_account_rate_rules(),
        client_key=f"messaging-account:{account_id}",
        scope_key=f"messaging-webhook:{platform}:account",
        trace=trace,
    )


async def dispatch_authenticated_events(
    request: Request,
    api_context: ApiContext,
    *,
    account_id: str,
    events: tuple[NormalizedMessagingEvent, ...],
    trace: MessagingWebhookTrace,
) -> JSONResponse:
    if len(events) > MESSAGING_WEBHOOK_MAX_EVENTS:
        log_messaging_webhook_complete(
            trace,
            outcome="rejected",
            event_count=len(events),
            failure_code="messaging_webhook_event_limit_exceeded",
        )
        raise_invalid_request(request, "Messaging webhook contains too many events.")
    outcomes: dict[str, int] = {}
    for event in events:
        _enforce_authenticated_rate(
            request,
            rules=_sender_rate_rules(),
            client_key=f"messaging-account:{account_id}:sender:{event.sender_id or 'protocol'}",
            scope_key=f"messaging-webhook:{event.platform}:sender",
            trace=trace,
            classification=event.classification,
        )
        try:
            result = await api_context.dependencies.messaging_gateway.admit_event(
                account_id=account_id,
                event=event,
            )
        except HANDLED_RUNTIME_EXCEPTIONS:
            log_messaging_webhook_complete(
                trace,
                outcome="failure",
                failure_code="messaging_webhook_admission_failed",
            )
            raise
        status_value = result.get("status")
        status = status_value if isinstance(status_value, str) else "failed"
        outcomes[status] = outcomes.get(status, 0) + 1
        log_messaging_webhook_admission(
            trace,
            event,
            admission_status=status,
        )
    log_messaging_webhook_complete(
        trace,
        outcome="success",
        event_count=len(events),
    )
    return JSONResponse(content={"ok": True, "count": len(events), "outcomes": outcomes})
