"""SoAI - Messaging runtime account inventory and readiness boundary [backend/app/background/messaging_runtime_inventory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from app.background.runtime_api_dependencies import (
    resolve_api_dependencies_from_runtime,
)
from core.logging.trace import get_logger
from core.messaging.observability_emission import (
    log_messaging_diagnostic,
    log_messaging_trace,
)
from core.messaging.observability_fields import MessagingLogFields
from core.runtime.network_policy import is_offline_mode_enabled
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from core.messaging.protocols import DatabaseMessagingAccountsProtocol
    from core.runtime.protocols import (
        RuntimeFlagsViewProtocol,
        RuntimeStateStoreProtocol,
    )
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("MessagingRuntimeInventory", "load_messaging_runtime_inventory")

LOGGER_NAME = "SoAI.app.background.messaging_runtime_inventory"
OPERATION_INVENTORY = "messaging.gateway.runtime_inventory"


@dataclass(frozen=True, slots=True)
class MessagingRuntimeInventory:
    api_dependencies: ApiDependencies
    public_origin: str
    webhook_accounts: tuple[JSONDict, ...]
    discord_accounts: tuple[JSONDict, ...]


async def load_messaging_runtime_inventory(
    *,
    runtime_state: RuntimeStateStoreProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    database_accounts: DatabaseMessagingAccountsProtocol,
) -> MessagingRuntimeInventory:
    logger = get_logger(LOGGER_NAME)
    started_ms = monotonic_ms()
    readiness_waited = not runtime_state.startup_ready_event.is_set()
    if readiness_waited:
        log_messaging_diagnostic(
            logger,
            message="Messaging runtime is waiting for API startup readiness.",
            log_fields=MessagingLogFields(
                operation=OPERATION_INVENTORY,
                phase="start",
                outcome="retryable",
            ),
        )
    api_dependencies = await resolve_api_dependencies_from_runtime(runtime_state)
    if readiness_waited:
        log_messaging_diagnostic(
            logger,
            message="Messaging runtime API startup readiness was reached.",
            log_fields=MessagingLogFields(
                operation=OPERATION_INVENTORY,
                phase="progress",
                outcome="success",
                elapsed_ms=monotonic_ms() - started_ms,
            ),
        )
    public_origin = api_dependencies.config.get_str("SERVER.PUBLIC_ORIGIN") or ""
    webhook_accounts: list[JSONDict] = []
    discord_accounts: list[JSONDict] = []
    if not is_offline_mode_enabled(runtime_flags):
        for platform in ("telegram", "whatsapp"):
            webhook_accounts.extend(
                await database_accounts.list_reconcilable_transport_accounts(platform),
            )
        discord_accounts = await database_accounts.list_enabled_transport_accounts("discord")
    log_messaging_trace(
        logger,
        message="Messaging runtime account inventory loaded.",
        log_fields=replace(
            MessagingLogFields(
                operation=OPERATION_INVENTORY,
                phase="complete",
                outcome="success",
            ),
            account_count=len(webhook_accounts) + len(discord_accounts),
            elapsed_ms=monotonic_ms() - started_ms,
        ),
    )
    return MessagingRuntimeInventory(
        api_dependencies=api_dependencies,
        public_origin=public_origin,
        webhook_accounts=tuple(webhook_accounts),
        discord_accounts=tuple(discord_accounts),
    )
