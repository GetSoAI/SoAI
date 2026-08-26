"""SoAI - Discord Gateway operation routing [backend/app/background/messaging_gateway_discord_protocol.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import secrets
from dataclasses import replace
from typing import TYPE_CHECKING

from websockets.asyncio.client import ClientConnection

from app.background.messaging_gateway_discord_dispatch import commit_discord_dispatch
from app.background.messaging_gateway_discord_heartbeat import (
    DiscordHeartbeatState,
    send_discord_heartbeat,
    send_discord_payload,
)
from core.concurrency.shutdown_waits import wait_for_shutdown_or_schedule_change
from core.errors.exceptions import ServiceUnavailableError, ValidationError
from core.logging.trace import get_logger
from core.messaging.discord_gateway_payload import parse_discord_gateway_payload
from core.messaging.discord_gateway_state import (
    build_discord_online_presence,
    read_discord_dispatch_sequence,
    read_discord_operation_code,
)
from core.messaging.observability_emission import log_messaging_diagnostic
from core.messaging.observability_fields import MessagingLogFields
from core.runtime.network_policy import is_offline_mode_enabled
from core.timing.constants import STANDARD_DELAY_SEC
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from core.messaging.discord_gateway_state import (
        DiscordConnectionContext,
        DiscordReconnectMode,
    )
    from core.messaging.protocols import DatabaseMessagingIngressProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "discord_connection_fields",
    "log_discord_reconnect_decision",
    "receive_discord_payload",
    "route_discord_gateway_events",
)

LOGGER_NAME = "SoAI.app.background.messaging_gateway_discord_protocol"
OPERATION_CONNECTION = "messaging.discord.connection"


def discord_connection_fields(context: DiscordConnectionContext) -> MessagingLogFields:
    return MessagingLogFields(
        operation=OPERATION_CONNECTION,
        platform="discord",
        account_id=context.account_id,
        revision=context.revision,
        lifecycle_generation=context.lifecycle_generation,
        connection_generation=context.connection_generation,
        start_mode=context.start_mode,
    )


def log_discord_reconnect_decision(
    context: DiscordConnectionContext,
    *,
    reconnect_mode: DiscordReconnectMode,
    failure_code: str | None,
    operation_code: int | None = None,
    close_code: int | None = None,
) -> None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Discord Gateway connection ended.",
        log_fields=replace(
            discord_connection_fields(context),
            phase="complete",
            outcome="success" if reconnect_mode == "stop" else "retryable",
            operation_code=operation_code,
            close_code=close_code,
            outcome_detail=reconnect_mode,
            failure_code=failure_code,
            elapsed_ms=monotonic_ms() - context.started_monotonic_ms,
        ),
    )


async def receive_discord_payload(
    websocket: ClientConnection,
    timeout_seconds: float,
) -> JSONDict:
    raw_payload = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
    return parse_discord_gateway_payload(raw_payload)


async def _handle_invalid_session(
    *,
    messaging_ingress: DatabaseMessagingIngressProtocol,
    context: DiscordConnectionContext,
    payload: JSONDict,
    shutdown_event: asyncio.Event,
) -> DiscordReconnectMode:
    resumable = payload.get("d") is True
    if not resumable:
        await messaging_ingress.mark_discord_session_gap(
            account_id=context.account_id,
            connection_generation=context.connection_generation,
        )
    wait_outcome = await wait_for_shutdown_or_schedule_change(
        shutdown_event,
        None,
        secrets.SystemRandom().uniform(1.0, 5.0),
    )
    if wait_outcome != "timeout":
        log_discord_reconnect_decision(
            context,
            reconnect_mode="stop",
            failure_code=None,
            operation_code=9,
        )
        return "stop"
    reconnect_mode: DiscordReconnectMode = "resume" if resumable else "identify"
    log_discord_reconnect_decision(
        context,
        reconnect_mode=reconnect_mode,
        failure_code="discord_invalid_session",
        operation_code=9,
    )
    return reconnect_mode


async def _accepts_dispatch_sequence(
    *,
    messaging_ingress: DatabaseMessagingIngressProtocol,
    context: DiscordConnectionContext,
    state: DiscordHeartbeatState,
    sequence: int,
) -> bool:
    latest_received_sequence = state.latest_received_sequence
    if latest_received_sequence is None:
        return True
    if sequence < latest_received_sequence:
        log_messaging_diagnostic(
            get_logger(LOGGER_NAME),
            message="Discord Dispatch sequence regressed.",
            log_fields=replace(
                discord_connection_fields(context),
                phase="progress",
                outcome="rejected",
                dispatch_sequence=sequence,
                failure_code="discord_dispatch_sequence_regressed",
            ),
        )
        raise ValidationError("Discord Dispatch sequence regressed.")
    if sequence > latest_received_sequence + 1:
        await messaging_ingress.mark_discord_session_gap(
            account_id=context.account_id,
            connection_generation=context.connection_generation,
        )
        log_discord_reconnect_decision(
            context,
            reconnect_mode="identify",
            failure_code="discord_dispatch_sequence_gap",
        )
        return False
    return True


async def _resolve_heartbeat_stop(
    *,
    context: DiscordConnectionContext,
    state: DiscordHeartbeatState,
    heartbeat_task: asyncio.Task[None],
) -> DiscordReconnectMode:
    await heartbeat_task
    if not state.reconnect_requested.is_set():
        raise ServiceUnavailableError("Discord heartbeat stopped unexpectedly.")
    log_discord_reconnect_decision(
        context,
        reconnect_mode="resume",
        failure_code="discord_heartbeat_ack_missing",
    )
    return "resume"


async def route_discord_gateway_events(
    *,
    runtime_flags: RuntimeFlagsViewProtocol,
    messaging_ingress: DatabaseMessagingIngressProtocol,
    api_dependencies: ApiDependencies,
    context: DiscordConnectionContext,
    websocket: ClientConnection,
    state: DiscordHeartbeatState,
    heartbeat_task: asyncio.Task[None],
    shutdown_event: asyncio.Event,
) -> DiscordReconnectMode:
    while not shutdown_event.is_set() and not is_offline_mode_enabled(runtime_flags):
        if heartbeat_task.done():
            return await _resolve_heartbeat_stop(
                context=context,
                state=state,
                heartbeat_task=heartbeat_task,
            )
        try:
            payload = await receive_discord_payload(websocket, STANDARD_DELAY_SEC)
        except TimeoutError:
            continue
        operation_code = read_discord_operation_code(payload)
        log_messaging_diagnostic(
            get_logger(LOGGER_NAME),
            message="Discord Gateway operation received.",
            log_fields=replace(
                discord_connection_fields(context),
                phase="progress",
                outcome="success",
                operation_code=operation_code,
            ),
        )
        if operation_code == 11:
            state.acknowledged = True
            last_sent = state.last_sent_monotonic
            log_messaging_diagnostic(
                get_logger(LOGGER_NAME),
                message="Discord Gateway heartbeat acknowledged.",
                log_fields=replace(
                    discord_connection_fields(context),
                    phase="progress",
                    outcome="success",
                    operation_code=11,
                    elapsed_ms=(
                        int((asyncio.get_running_loop().time() - last_sent) * 1000)
                        if last_sent is not None
                        else None
                    ),
                ),
            )
            continue
        if operation_code == 1:
            await send_discord_heartbeat(
                websocket,
                state,
                context=context,
                requested_by_provider=True,
            )
            continue
        if operation_code == 7:
            log_discord_reconnect_decision(
                context,
                reconnect_mode="resume",
                failure_code="discord_reconnect_requested",
                operation_code=7,
            )
            return "resume"
        if operation_code == 9:
            return await _handle_invalid_session(
                messaging_ingress=messaging_ingress,
                context=context,
                payload=payload,
                shutdown_event=shutdown_event,
            )
        if operation_code != 0:
            continue
        sequence = read_discord_dispatch_sequence(payload)
        if not await _accepts_dispatch_sequence(
            messaging_ingress=messaging_ingress,
            context=context,
            state=state,
            sequence=sequence,
        ):
            return "identify"
        state.latest_received_sequence = sequence
        if payload.get("t") in ("READY", "RESUMED"):
            async with state.send_lock:
                await send_discord_payload(
                    websocket,
                    {"op": 3, "d": build_discord_online_presence()},
                )
        await commit_discord_dispatch(
            messaging_ingress=messaging_ingress,
            api_dependencies=api_dependencies,
            context=context,
            payload=payload,
        )
    log_discord_reconnect_decision(context, reconnect_mode="stop", failure_code=None)
    return "stop"
