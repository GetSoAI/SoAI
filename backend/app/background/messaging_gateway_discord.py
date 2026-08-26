"""SoAI - Discord Gateway WebSocket connection lifecycle [backend/app/background/messaging_gateway_discord.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed

from app.background.messaging_gateway_discord_heartbeat import (
    DiscordHeartbeatState,
    run_discord_heartbeat,
    send_discord_payload,
)
from app.background.messaging_gateway_discord_protocol import (
    discord_connection_fields,
    log_discord_reconnect_decision,
    receive_discord_payload,
    route_discord_gateway_events,
)
from core.concurrency.task_finalization import cancel_and_await_task
from core.errors.exceptions import ServiceUnavailableError, ValidationError
from core.logging.trace import get_logger
from core.messaging.discord_gateway_payload import (
    resolve_discord_heartbeat_interval_sec,
)
from core.messaging.discord_gateway_state import (
    read_discord_operation_code,
    resolve_discord_close_action,
)
from core.messaging.observability_emission import log_messaging_diagnostic
from core.runtime.websocket_policy import validate_runtime_websocket_url
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
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

__all__ = ("run_discord_gateway_connection",)

LOGGER_NAME = "SoAI.app.background.messaging_gateway_discord"


async def _resolve_hello_interval(
    websocket: ClientConnection,
    context: DiscordConnectionContext,
) -> float:
    hello = await receive_discord_payload(websocket, INTERACTIVE_TIMEOUT_SEC)
    if read_discord_operation_code(hello) != 10:
        raise ValidationError("Discord Gateway did not begin with HELLO.")
    hello_data = hello.get("d")
    if not isinstance(hello_data, dict):
        raise ValidationError("Discord HELLO data is invalid.")
    heartbeat_interval = resolve_discord_heartbeat_interval_sec(hello_data)
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Discord Gateway HELLO received.",
        log_fields=replace(
            discord_connection_fields(context),
            phase="progress",
            outcome="success",
            operation_code=10,
            interval_ms=int(heartbeat_interval * 1000),
            elapsed_ms=monotonic_ms() - context.started_monotonic_ms,
        ),
    )
    return heartbeat_interval


async def _handle_connection_closed(
    *,
    messaging_ingress: DatabaseMessagingIngressProtocol,
    context: DiscordConnectionContext,
    exception: ConnectionClosed,
) -> DiscordReconnectMode:
    received_close = exception.rcvd
    sent_close = exception.sent
    close_code = (
        received_close.code
        if received_close is not None
        else sent_close.code if sent_close is not None else None
    )
    close_action = resolve_discord_close_action(close_code)
    log_discord_reconnect_decision(
        context,
        reconnect_mode=close_action,
        failure_code="discord_connection_closed",
        close_code=close_code,
    )
    if close_action == "resume":
        return "resume"
    await messaging_ingress.mark_discord_session_gap(
        account_id=context.account_id,
        connection_generation=context.connection_generation,
    )
    return close_action


async def _run_established_connection(
    *,
    runtime_flags: RuntimeFlagsViewProtocol,
    messaging_ingress: DatabaseMessagingIngressProtocol,
    api_dependencies: ApiDependencies,
    context: DiscordConnectionContext,
    websocket: ClientConnection,
    start_payload: JSONDict,
    committed_sequence: int | None,
    shutdown_event: asyncio.Event,
) -> DiscordReconnectMode:
    heartbeat_interval = await _resolve_hello_interval(websocket, context)
    await send_discord_payload(websocket, start_payload)
    heartbeat_state = DiscordHeartbeatState(latest_received_sequence=committed_sequence)
    heartbeat_task = asyncio.create_task(
        run_discord_heartbeat(
            websocket=websocket,
            state=heartbeat_state,
            context=context,
            heartbeat_interval=heartbeat_interval,
            shutdown_event=shutdown_event,
        ),
        name=f"discord-heartbeat-{context.account_id}",
    )
    try:
        return await route_discord_gateway_events(
            runtime_flags=runtime_flags,
            messaging_ingress=messaging_ingress,
            api_dependencies=api_dependencies,
            context=context,
            websocket=websocket,
            state=heartbeat_state,
            heartbeat_task=heartbeat_task,
            shutdown_event=shutdown_event,
        )
    finally:
        await cancel_and_await_task(heartbeat_task)


async def run_discord_gateway_connection(
    *,
    runtime_flags: RuntimeFlagsViewProtocol,
    messaging_ingress: DatabaseMessagingIngressProtocol,
    api_dependencies: ApiDependencies,
    context: DiscordConnectionContext,
    gateway_url: str,
    start_payload: JSONDict,
    committed_sequence: int | None,
    shutdown_event: asyncio.Event,
) -> DiscordReconnectMode:
    pinned_host = await validate_runtime_websocket_url(
        runtime_flags,
        gateway_url,
        source="Discord messaging Gateway",
    )
    if pinned_host is not None:
        websocket_connection = websockets.connect(
            gateway_url,
            max_queue=1,
            host=pinned_host,
            proxy=None,
        )
    else:
        websocket_connection = websockets.connect(gateway_url, max_queue=1, proxy=None)
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Discord Gateway connection opening.",
        log_fields=replace(
            discord_connection_fields(context),
            phase="start",
            dispatch_sequence=committed_sequence,
        ),
    )
    try:
        async with websocket_connection as websocket:
            return await _run_established_connection(
                runtime_flags=runtime_flags,
                messaging_ingress=messaging_ingress,
                api_dependencies=api_dependencies,
                context=context,
                websocket=websocket,
                start_payload=start_payload,
                committed_sequence=committed_sequence,
                shutdown_event=shutdown_event,
            )
    except ConnectionClosed as exception:
        return await _handle_connection_closed(
            messaging_ingress=messaging_ingress,
            context=context,
            exception=exception,
        )
    except OSError as exception:
        log_messaging_diagnostic(
            get_logger(LOGGER_NAME),
            message="Discord Gateway connection could not be established.",
            log_fields=replace(
                discord_connection_fields(context),
                phase="complete",
                outcome="retryable",
                failure_code="discord_gateway_connect_failed",
                elapsed_ms=monotonic_ms() - context.started_monotonic_ms,
            ),
        )
        raise ServiceUnavailableError("Discord Gateway connection failed.") from exception
