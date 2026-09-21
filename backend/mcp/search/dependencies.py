"""SoAI - MCP search dependencies [backend/mcp/search/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

import httpx2
from cryptography.fernet import Fernet

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)
from core.users.protocols_database import DatabaseUsersProtocol
from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol
from mcp.search.clients.client_base import SearchClientBase

__all__ = ("MCPSearchDependencies",)


@dataclass(frozen=True, slots=True)
class MCPSearchDependencies:
    config: ConfigProtocol
    database_users: DatabaseUsersProtocol
    database_plugins: DatabasePluginsProtocol
    fernet: tuple[Fernet, ...]
    http_client: httpx2.AsyncClient
    runtime_flags: RuntimeFlagsViewProtocol
    task_registry: TaskRegistryProtocol
    event_bus: EventBusProtocol
    metrics_manager: MetricsManagerProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    token_collection: TokenCollectionProtocol
    web_fetcher: WebContentFetcherProtocol
    search_providers: tuple[tuple[str, type[SearchClientBase]], ...]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPSearchDependencies",
            cancellation_event_bus=self.cancellation_event_bus,
            cancellation_history=self.cancellation_history,
            config=self.config,
            database_users=self.database_users,
            database_plugins=self.database_plugins,
            event_bus=self.event_bus,
            fernet=self.fernet,
            http_client=self.http_client,
            metrics_manager=self.metrics_manager,
            runtime_flags=self.runtime_flags,
            search_providers=self.search_providers,
            task_registry=self.task_registry,
            token_collection=self.token_collection,
            web_fetcher=self.web_fetcher,
        )
