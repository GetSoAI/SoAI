"""SoAI - Discord Gateway resume and identify target selection [backend/app/background/messaging_gateway_discord_target.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.concurrency.shutdown_waits import wait_for_shutdown_or_schedule_change
from core.errors.exceptions import ServiceUnavailableError
from core.logging.trace import get_logger
from core.messaging.discord_gateway_state import (
    DiscordGatewayDiscovery,
    build_discord_gateway_url,
    build_discord_identify_payload,
    build_discord_resume_payload,
)
from core.messaging.observability_emission import log_messaging_diagnostic
from core.messaging.observability_fields import MessagingLogFields
from core.timing.monotonic import monotonic_ms
from features.messaging.discord_gateway_discovery import fetch_discord_gateway_discovery

if TYPE_CHECKING:
    import httpx2

    from core.messaging.discord_gateway_state import DiscordStartMode
    from core.types.json import JSONDict

__all__ = ("DiscordConnectionTarget", "resolve_discord_connection_target")

LOGGER_NAME = "SoAI.app.background.messaging_gateway_discord_target"
OPERATION_START_TARGET = "messaging.discord.start_target"


@dataclass(frozen=True, slots=True)
class DiscordConnectionTarget:
    gateway_url: str
    start_payload: JSONDict
    start_mode: DiscordStartMode


def _resume_target(token: str, session: JSONDict) -> DiscordConnectionTarget | None:
    session_id = session.get("session_id")
    resume_url = session.get("resume_gateway_url")
    committed_sequence = session.get("committed_dispatch_sequence")
    if (
        session.get("session_state") != "resumable"
        or not isinstance(session_id, str)
        or not isinstance(resume_url, str)
        or isinstance(committed_sequence, bool)
        or not isinstance(committed_sequence, int)
    ):
        return None
    return DiscordConnectionTarget(
        gateway_url=build_discord_gateway_url(resume_url),
        start_payload=build_discord_resume_payload(
            token=token,
            session_id=session_id,
            dispatch_sequence=committed_sequence,
        ),
        start_mode="resume",
    )


async def _await_identify_budget(
    *,
    http_client: httpx2.AsyncClient,
    token: str,
    log_fields: MessagingLogFields,
    discovery: DiscordGatewayDiscovery,
    shutdown_event: asyncio.Event,
) -> DiscordGatewayDiscovery | None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Discord Gateway identify budget is exhausted; waiting for the reset window.",
        log_fields=replace(
            log_fields,
            phase="progress",
            outcome="retryable",
            start_mode="identify",
            failure_code="discord_identify_budget_exhausted",
            retry_after_ms=discovery.session_start_reset_after_ms,
        ),
    )
    wait_outcome = await wait_for_shutdown_or_schedule_change(
        shutdown_event,
        None,
        discovery.session_start_reset_after_ms / 1000.0,
    )
    if wait_outcome != "timeout":
        return None
    refreshed = await fetch_discord_gateway_discovery(http_client, token)
    if refreshed.session_starts_remaining == 0:
        raise ServiceUnavailableError("Discord identify session limit remains exhausted.")
    return refreshed


async def resolve_discord_connection_target(
    *,
    http_client: httpx2.AsyncClient,
    token: str,
    account_id: str,
    session: JSONDict,
    shutdown_event: asyncio.Event,
) -> DiscordConnectionTarget | None:
    logger = get_logger(LOGGER_NAME)
    log_fields = MessagingLogFields(
        operation=OPERATION_START_TARGET,
        platform="discord",
        account_id=account_id,
    )
    resume_target = _resume_target(token, session)
    if resume_target is not None:
        log_messaging_diagnostic(
            logger,
            message="Discord Gateway will resume its existing session.",
            log_fields=replace(
                log_fields,
                phase="complete",
                outcome="success",
                start_mode="resume",
            ),
        )
        return resume_target
    started_ms = monotonic_ms()
    discovery = await fetch_discord_gateway_discovery(http_client, token)
    log_messaging_diagnostic(
        logger,
        message="Discord Gateway discovery resolved its session-start limits.",
        log_fields=replace(
            log_fields,
            phase="progress",
            outcome="success",
            start_mode="identify",
            elapsed_ms=monotonic_ms() - started_ms,
            budget_remaining=discovery.session_starts_remaining,
            max_concurrency=discovery.identify_max_concurrency,
            retry_after_ms=discovery.session_start_reset_after_ms,
        ),
    )
    if discovery.session_starts_remaining == 0:
        refreshed = await _await_identify_budget(
            http_client=http_client,
            token=token,
            log_fields=log_fields,
            discovery=discovery,
            shutdown_event=shutdown_event,
        )
        if refreshed is None:
            return None
        discovery = refreshed
    log_messaging_diagnostic(
        logger,
        message="Discord Gateway will start a new session.",
        log_fields=replace(
            log_fields,
            phase="complete",
            outcome="success",
            start_mode="identify",
            elapsed_ms=monotonic_ms() - started_ms,
        ),
    )
    return DiscordConnectionTarget(
        gateway_url=build_discord_gateway_url(discovery.gateway_url),
        start_payload=build_discord_identify_payload(token),
        start_mode="identify",
    )
