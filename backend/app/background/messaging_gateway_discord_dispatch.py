"""SoAI - Discord Gateway Dispatch commitment [backend/app/background/messaging_gateway_discord_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.messaging.discord_gateway_state import read_discord_ready_state
from core.messaging.discord_normalization import normalize_discord_gateway_dispatch
from core.messaging.observability_emission import (
    log_messaging_diagnostic,
    log_messaging_lifecycle,
)
from core.messaging.observability_fields import MessagingLogFields
from core.timing.monotonic import monotonic_ms
from features.messaging.account_runtime_health import (
    record_messaging_account_runtime_health,
)
from features.messaging.ingress_publication import publish_messaging_admission

if TYPE_CHECKING:
    from core.messaging.discord_gateway_state import DiscordConnectionContext
    from core.messaging.protocols import DatabaseMessagingIngressProtocol
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("commit_discord_dispatch",)

LOGGER_NAME = "SoAI.app.background.messaging_gateway_discord_dispatch"
OPERATION_DISPATCH = "messaging.discord.dispatch"
OPERATION_READY = "messaging.discord.ready"
OPERATION_RESUMED = "messaging.discord.resumed"


def _dispatch_fields(context: DiscordConnectionContext) -> MessagingLogFields:
    return MessagingLogFields(
        operation=OPERATION_DISPATCH,
        platform="discord",
        account_id=context.account_id,
        revision=context.revision,
        lifecycle_generation=context.lifecycle_generation,
        connection_generation=context.connection_generation,
    )


async def commit_discord_dispatch(
    *,
    messaging_ingress: DatabaseMessagingIngressProtocol,
    api_dependencies: ApiDependencies,
    context: DiscordConnectionContext,
    payload: JSONDict,
) -> None:
    events = normalize_discord_gateway_dispatch(payload)
    if len(events) != 1:
        log_messaging_diagnostic(
            get_logger(LOGGER_NAME),
            message="Discord Dispatch could not be normalized.",
            log_fields=replace(
                _dispatch_fields(context),
                phase="complete",
                outcome="rejected",
                failure_code="discord_dispatch_not_normalizable",
                event_count=len(events),
            ),
        )
        raise ValidationError("Discord Dispatch could not be normalized durably.")
    event = events[0]
    event_type = payload.get("t")
    is_ready = event_type == "READY"
    if is_ready:
        ready_state = read_discord_ready_state(payload)
        result = await messaging_ingress.record_discord_ready(
            account_id=context.account_id,
            connection_generation=context.connection_generation,
            event=event,
            session_id=ready_state.session_id,
            resume_gateway_url=ready_state.resume_gateway_url,
        )
    else:
        result = await messaging_ingress.commit_discord_dispatch(
            account_id=context.account_id,
            connection_generation=context.connection_generation,
            event=event,
        )
    admission_status = result.get("status")
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Discord Dispatch committed.",
        log_fields=replace(
            _dispatch_fields(context),
            phase="complete",
            outcome="success",
            dispatch_sequence=event.discord_dispatch_sequence,
            classification=event.classification,
            remote_thread_type=event.remote_thread_type,
            admission_status=(admission_status if isinstance(admission_status, str) else "unknown"),
        ),
    )
    await publish_messaging_admission(api_dependencies, result)
    if event_type not in ("READY", "RESUMED"):
        return
    log_messaging_lifecycle(
        get_logger(LOGGER_NAME),
        message=(
            "Discord Gateway reached READY." if is_ready else "Discord Gateway session resumed."
        ),
        log_fields=replace(
            _dispatch_fields(context),
            operation=OPERATION_READY if is_ready else OPERATION_RESUMED,
            phase="complete",
            outcome="success",
            start_mode=context.start_mode,
            elapsed_ms=monotonic_ms() - context.started_monotonic_ms,
        ),
    )
    await record_messaging_account_runtime_health(
        api_dependencies,
        platform="discord",
        account_id=context.account_id,
        expected_revision=context.revision,
        lifecycle_generation=context.lifecycle_generation,
        healthy=True,
        health_code=None,
    )
