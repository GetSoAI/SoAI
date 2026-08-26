"""SoAI - Account-scoped Messaging webhook routes [backend/features/api/routes/messaging/messaging_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from core.messaging.platform_verification import parse_whatsapp_verification_challenge
from core.messaging.telegram_normalization import normalize_telegram_update
from core.messaging.whatsapp_normalization import normalize_whatsapp_webhook_payload
from core.validation.strings import coerce_optional_trimmed_str
from features.api.routes.messaging.webhook_admission import (
    dispatch_authenticated_events,
    enforce_authenticated_account_rate,
)
from features.api.routes.messaging.webhook_observability import (
    begin_messaging_webhook_trace,
    log_messaging_webhook_authentication,
    log_messaging_webhook_complete,
    log_messaging_webhook_normalization,
)
from features.api.routes.messaging.webhook_requests import (
    load_webhook_account,
    parse_messaging_webhook_body,
    read_messaging_webhook_body_bytes,
    require_account_credentials,
    require_telegram_webhook_secret,
    require_whatsapp_webhook_signature,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_forbidden

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    router = routers.messaging

    @router.post("/telegram/webhook")
    async def telegram_webhook(
        request: Request,
        account_id: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        trace = begin_messaging_webhook_trace(
            request,
            platform="telegram",
            account_id=account_id,
            operation="messaging.telegram.webhook",
        )
        account = await load_webhook_account(
            request,
            api_context,
            account_id=account_id,
            platform="telegram",
            trace=trace,
        )
        require_telegram_webhook_secret(
            request,
            account=account,
            provided_token=request.headers.get("x-telegram-bot-api-secret-token"),
            trace=trace,
        )
        enforce_authenticated_account_rate(
            request,
            account_id=account_id,
            platform="telegram",
            trace=trace,
        )
        raw_body = await read_messaging_webhook_body_bytes(request, trace)
        payload = parse_messaging_webhook_body(request, raw_body, trace)
        events = normalize_telegram_update(payload)
        log_messaging_webhook_normalization(trace, events)
        return await dispatch_authenticated_events(
            request,
            api_context,
            account_id=account_id,
            events=events,
            trace=trace,
        )

    @router.get("/whatsapp/webhook")
    async def whatsapp_webhook_verify(
        request: Request,
        account_id: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> PlainTextResponse:
        trace = begin_messaging_webhook_trace(
            request,
            platform="whatsapp",
            account_id=account_id,
            operation="messaging.whatsapp.webhook_verify",
        )
        account = await load_webhook_account(
            request,
            api_context,
            account_id=account_id,
            platform="whatsapp",
            trace=trace,
        )
        credentials = require_account_credentials(account)
        response_challenge = parse_whatsapp_verification_challenge(
            verify_token=coerce_optional_trimmed_str(credentials.get("verify_token")),
            mode=request.query_params.get("hub.mode"),
            token=request.query_params.get("hub.verify_token"),
            challenge=request.query_params.get("hub.challenge"),
        )
        if response_challenge is None:
            log_messaging_webhook_authentication(
                trace,
                accepted=False,
                failure_code="whatsapp_webhook_verification_invalid",
            )
            log_messaging_webhook_complete(
                trace,
                outcome="rejected",
                failure_code="whatsapp_webhook_verification_invalid",
            )
            raise_forbidden(request, "WhatsApp webhook verification failed.")
        log_messaging_webhook_authentication(trace, accepted=True)
        log_messaging_webhook_complete(trace, outcome="success")
        return PlainTextResponse(content=response_challenge)

    @router.post("/whatsapp/webhook")
    async def whatsapp_webhook(
        request: Request,
        account_id: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        trace = begin_messaging_webhook_trace(
            request,
            platform="whatsapp",
            account_id=account_id,
            operation="messaging.whatsapp.webhook",
        )
        account = await load_webhook_account(
            request,
            api_context,
            account_id=account_id,
            platform="whatsapp",
            trace=trace,
        )
        raw_body = await read_messaging_webhook_body_bytes(request, trace)
        require_whatsapp_webhook_signature(
            request,
            account=account,
            signature_header=request.headers.get("x-hub-signature-256"),
            raw_body=raw_body,
            trace=trace,
        )
        enforce_authenticated_account_rate(
            request,
            account_id=account_id,
            platform="whatsapp",
            trace=trace,
        )
        payload = parse_messaging_webhook_body(request, raw_body, trace)
        events = normalize_whatsapp_webhook_payload(payload)
        log_messaging_webhook_normalization(trace, events)
        return await dispatch_authenticated_events(
            request,
            api_context,
            account_id=account_id,
            events=events,
            trace=trace,
        )
