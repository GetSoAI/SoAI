"""SoAI - Discord account reconnect lifecycle [backend/app/background/messaging_gateway_discord_account.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import httpx2

from app.background.messaging_gateway_discord import run_discord_gateway_connection
from app.background.messaging_gateway_discord_target import (
    resolve_discord_connection_target,
)
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.messaging.discord_gateway_state import DiscordConnectionContext
from core.messaging.observability_emission import log_messaging_bounded_failure
from core.messaging.observability_fields import MessagingLogFields
from core.runtime.network_policy import is_offline_mode_enabled
from core.timing.monotonic import monotonic_ms
from features.messaging.account_recovery_backoff import (
    wait_for_messaging_account_recovery,
)
from features.messaging.account_runtime_health import (
    record_messaging_account_runtime_health,
)

if TYPE_CHECKING:
    from core.messaging.protocols import DatabaseMessagingIngressProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("DiscordGatewayAccountDependencies", "run_discord_gateway_account")

LOGGER_NAME = "SoAI.app.background.messaging_gateway_discord_account"
OPERATION_ACCOUNT_RUNTIME = "messaging.discord.account_runtime"
FAILURE_SUMMARY_INTERVAL_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class DiscordGatewayAccountDependencies:
    runtime_flags: RuntimeFlagsViewProtocol
    http_client: httpx2.AsyncClient
    messaging_ingress: DatabaseMessagingIngressProtocol
    api_dependencies: ApiDependencies

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DiscordGatewayAccountDependencies",
            runtime_flags=self.runtime_flags,
            http_client=self.http_client,
            messaging_ingress=self.messaging_ingress,
            api_dependencies=self.api_dependencies,
        )


async def _run_discord_connection_cycle(
    *,
    deps: DiscordGatewayAccountDependencies,
    account_id: str,
    user_id: int,
    revision: int,
    lifecycle_generation: int,
    bot_token: str,
    shutdown_event: asyncio.Event,
) -> bool:
    session = await deps.messaging_ingress.begin_discord_connection(
        account_id=account_id,
        user_id=user_id,
    )
    generation = session.get("connection_generation")
    if not isinstance(generation, int):
        raise ValidationError("Discord connection generation is invalid.")
    target = await resolve_discord_connection_target(
        http_client=deps.http_client,
        token=bot_token,
        account_id=account_id,
        session=session,
        shutdown_event=shutdown_event,
    )
    if target is None:
        return False
    committed = session.get("committed_dispatch_sequence")
    reconnect_mode = await run_discord_gateway_connection(
        runtime_flags=deps.runtime_flags,
        messaging_ingress=deps.messaging_ingress,
        api_dependencies=deps.api_dependencies,
        context=DiscordConnectionContext(
            account_id=account_id,
            revision=revision,
            lifecycle_generation=lifecycle_generation,
            connection_generation=generation,
            start_mode=target.start_mode,
            started_monotonic_ms=monotonic_ms(),
        ),
        gateway_url=target.gateway_url,
        start_payload=target.start_payload,
        committed_sequence=committed if isinstance(committed, int) else None,
        shutdown_event=shutdown_event,
    )
    if reconnect_mode not in ("stop", "degraded"):
        return True
    await deps.messaging_ingress.close_discord_session(
        account_id=account_id,
        connection_generation=generation,
    )
    if reconnect_mode == "degraded":
        await record_messaging_account_runtime_health(
            deps.api_dependencies,
            platform="discord",
            account_id=account_id,
            expected_revision=revision,
            lifecycle_generation=lifecycle_generation,
            healthy=False,
            health_code="discord_gateway_configuration_rejected",
        )
        await shutdown_event.wait()
    return False


async def run_discord_gateway_account(
    *,
    deps: DiscordGatewayAccountDependencies,
    account_id: str,
    user_id: int,
    revision: int,
    lifecycle_generation: int,
    bot_token: str,
    shutdown_event: asyncio.Event,
) -> None:
    reconnect_attempt = 0
    failure_warning_emitted = False
    logger = get_logger(LOGGER_NAME)
    failure_limiter = RateLimitedLogger(interval_seconds=FAILURE_SUMMARY_INTERVAL_SECONDS)
    log_fields = MessagingLogFields(
        operation=OPERATION_ACCOUNT_RUNTIME,
        platform="discord",
        account_id=account_id,
    )
    while not shutdown_event.is_set() and not is_offline_mode_enabled(deps.runtime_flags):
        try:
            if not await _run_discord_connection_cycle(
                deps=deps,
                account_id=account_id,
                user_id=user_id,
                revision=revision,
                lifecycle_generation=lifecycle_generation,
                bot_token=bot_token,
                shutdown_event=shutdown_event,
            ):
                return
            reconnect_attempt = 0
            failure_warning_emitted = False
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            await record_messaging_account_runtime_health(
                deps.api_dependencies,
                platform="discord",
                account_id=account_id,
                expected_revision=revision,
                lifecycle_generation=lifecycle_generation,
                healthy=False,
                health_code="discord_gateway_unavailable",
            )
            if not failure_warning_emitted:
                log_exception(
                    logger,
                    exception,
                    message="Discord Gateway account is degraded; retrying with bounded backoff.",
                    operation=OPERATION_ACCOUNT_RUNTIME,
                    details={"account_id": account_id},
                    level="warning",
                )
                failure_warning_emitted = True
            log_messaging_bounded_failure(
                logger,
                failure_limiter,
                message="Discord Gateway account runtime keeps failing.",
                log_fields=replace(
                    log_fields,
                    phase="complete",
                    outcome="failure",
                    attempt=reconnect_attempt,
                    failure_code="discord_gateway_unavailable",
                ),
            )
        if not await wait_for_messaging_account_recovery(
            shutdown_event,
            reconnect_attempt,
            log_fields=log_fields,
        ):
            return
        reconnect_attempt += 1
