"""SoAI - Discord Gateway heartbeat ownership [backend/app/background/messaging_gateway_discord_heartbeat.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from websockets.asyncio.client import ClientConnection

from core.concurrency.shutdown_waits import wait_for_shutdown_or_schedule_change
from core.logging.trace import get_logger
from core.messaging.observability_emission import log_messaging_diagnostic
from core.messaging.observability_fields import MessagingLogFields
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.messaging.discord_gateway_state import DiscordConnectionContext
    from core.types.json import JSONDict

__all__ = (
    "DiscordHeartbeatState",
    "run_discord_heartbeat",
    "send_discord_heartbeat",
    "send_discord_payload",
)

LOGGER_NAME = "SoAI.app.background.messaging_gateway_discord_heartbeat"
OPERATION_HEARTBEAT = "messaging.discord.heartbeat"


@dataclass(slots=True)
class DiscordHeartbeatState:
    latest_received_sequence: int | None
    acknowledged: bool = True
    last_sent_monotonic: float | None = None
    reconnect_requested: asyncio.Event = field(default_factory=asyncio.Event)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def _heartbeat_fields(context: DiscordConnectionContext) -> MessagingLogFields:
    return MessagingLogFields(
        operation=OPERATION_HEARTBEAT,
        platform="discord",
        account_id=context.account_id,
        revision=context.revision,
        lifecycle_generation=context.lifecycle_generation,
        connection_generation=context.connection_generation,
    )


async def send_discord_payload(websocket: ClientConnection, payload: JSONDict) -> None:
    await asyncio.wait_for(
        websocket.send(serialize_json_compact_stable_strict(payload)),
        timeout=INTERACTIVE_TIMEOUT_SEC,
    )


async def send_discord_heartbeat(
    websocket: ClientConnection,
    state: DiscordHeartbeatState,
    *,
    context: DiscordConnectionContext,
    requested_by_provider: bool,
) -> None:
    async with state.send_lock:
        await send_discord_payload(
            websocket,
            {"op": 1, "d": state.latest_received_sequence},
        )
        state.acknowledged = False
        state.last_sent_monotonic = asyncio.get_running_loop().time()
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Discord Gateway heartbeat sent.",
        log_fields=replace(
            _heartbeat_fields(context),
            phase="progress",
            outcome="success",
            operation_code=1 if requested_by_provider else None,
            dispatch_sequence=state.latest_received_sequence,
        ),
    )


async def run_discord_heartbeat(
    *,
    websocket: ClientConnection,
    state: DiscordHeartbeatState,
    context: DiscordConnectionContext,
    heartbeat_interval: float,
    shutdown_event: asyncio.Event,
) -> None:
    event_loop = asyncio.get_running_loop()
    next_deadline = event_loop.time() + secrets.SystemRandom().random() * heartbeat_interval
    while not shutdown_event.is_set():
        wait_outcome = await wait_for_shutdown_or_schedule_change(
            shutdown_event,
            None,
            max(0.0, next_deadline - event_loop.time()),
        )
        if wait_outcome != "timeout":
            return
        last_sent = state.last_sent_monotonic
        if last_sent is not None and last_sent + heartbeat_interval > event_loop.time():
            next_deadline = last_sent + heartbeat_interval
            continue
        if not state.acknowledged:
            state.reconnect_requested.set()
            log_messaging_diagnostic(
                get_logger(LOGGER_NAME),
                message="Discord Gateway heartbeat acknowledgement was not received.",
                log_fields=replace(
                    _heartbeat_fields(context),
                    phase="complete",
                    outcome="retryable",
                    failure_code="discord_heartbeat_ack_missing",
                    interval_ms=int(heartbeat_interval * 1000),
                ),
            )
            return
        await send_discord_heartbeat(
            websocket,
            state,
            context=context,
            requested_by_provider=False,
        )
        next_deadline = event_loop.time() + heartbeat_interval
