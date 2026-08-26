"""SoAI - Database repository service for plugin lifecycle and state [backend/database/repositories/plugins/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol
from core.database.provider_mutation_requests import (
    ProviderMutationOutcome,
    ProviderMutationReplayRequest,
)
from core.events.protocols import EventBusProtocol
from core.state.compatibility import CompatibilityInfo
from core.state.state_names import PLUGIN_STATE_ABSENT
from database.repositories.plugins.backend_variants import (
    get_backend_variant_id_query,
    sync_set_backend_variant_id,
)
from database.repositories.plugins.catalog_reads import (
    get_all_listable_plugins_query,
    get_all_plugins_query,
    get_latest_plugin_usage_query,
    get_plugin_by_name_query,
)
from database.repositories.plugins.catalog_writes import (
    sync_add_or_update_plugin,
    sync_create_uploading_placeholder,
    sync_permanently_delete_plugin_record,
)
from database.repositories.plugins.clone_transaction_service import (
    DatabasePluginCloneTransactions,
)
from database.repositories.plugins.provider_methods import (
    read_provider_mutation_outcome_method,
)
from database.repositories.plugins.public_operations import DatabasePluginsOperations
from database.repositories.plugins.state import (
    get_incompatible_state,
    get_plugin_state_only_query,
    sync_clear_incompatibility,
    sync_mark_plugin_user_enabled_once,
    sync_mark_welcome_message_logged,
    sync_set_incompatibility,
    sync_set_incompatibility_override,
    sync_update_plugin_state,
    sync_update_plugin_state_batch,
)
from database.repositories.plugins.stats import compute_plugin_stats

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabasePlugins",)


class DatabasePlugins(DatabasePluginsOperations):
    core: DatabaseCoreProtocol
    config: ConfigProtocol
    event_bus: EventBusProtocol | None
    fernet: tuple[Fernet, ...]
    clone_transactions: DatabasePluginCloneTransactions

    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.config = deps.config
        self.event_bus = deps.event_bus
        self.fernet = deps.fernet
        self.clone_transactions = DatabasePluginCloneTransactions(deps.core)

    async def create_uploading_placeholder(self, plugin_name: str) -> bool:
        return await self.core.writer.queue_write_operation(
            sync_create_uploading_placeholder,
            plugin_name,
        )

    async def add_or_update_plugin(
        self,
        plugin_data: JSONDict,
        *,
        state: str | None = None,
        incompatibility: CompatibilityInfo | None = None,
        override: bool | None = None,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_add_or_update_plugin,
            plugin_data,
            state,
            incompatibility,
            override,
        )

    async def mark_as_absent(self, plugin_names: list[str]) -> None:
        if plugin_names:
            await self.core.writer.queue_write_operation(
                sync_update_plugin_state_batch,
                plugin_names,
                PLUGIN_STATE_ABSENT,
            )

    async def get_all_listable_plugins(self) -> list[JSONDict]:
        return await self.core.reader.execute_read(get_all_listable_plugins_query)

    async def get_all_plugins(self) -> list[JSONDict]:
        return await self.core.reader.execute_read(get_all_plugins_query)

    async def get_plugin_by_name(self, plugin_name: str) -> JSONDict | None:
        return await self.core.reader.execute_read(get_plugin_by_name_query, plugin_name)

    async def get_plugin_state(self, plugin_name: str) -> str | None:
        return await self.core.reader.execute_read(get_plugin_state_only_query, plugin_name)

    async def get_latest_plugin_usage(self) -> JSONDict | None:
        return await self.core.reader.execute_read(get_latest_plugin_usage_query)

    async def get_backend_variant_id(self, plugin_name: str) -> str | None:
        return await self.core.reader.execute_read(get_backend_variant_id_query, plugin_name)

    async def set_backend_variant_id(
        self,
        plugin_name: str,
        backend_variant_id: str,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_set_backend_variant_id,
            plugin_name,
            backend_variant_id,
        )

    async def update_plugin_state(
        self,
        plugin_name: str,
        state: str,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_update_plugin_state,
            plugin_name,
            state,
        )

    async def set_incompatibility(
        self,
        plugin_name: str,
        info: CompatibilityInfo,
        state: str | None = None,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_set_incompatibility,
            plugin_name,
            info,
            state or get_incompatible_state(),
        )

    async def clear_incompatibility(self, plugin_name: str) -> None:
        await self.core.writer.queue_write_operation(
            sync_clear_incompatibility,
            plugin_name,
        )

    async def set_incompatibility_override(
        self,
        plugin_name: str,
        override: bool,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_set_incompatibility_override,
            plugin_name,
            override,
        )

    async def permanently_delete_plugin_record(self, plugin_name: str) -> int:
        return await self.core.writer.queue_write_operation(
            sync_permanently_delete_plugin_record,
            plugin_name,
        )

    async def mark_welcome_message_logged(
        self,
        plugin_name: str,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_mark_welcome_message_logged,
            plugin_name,
        )

    async def mark_plugin_user_enabled_once(self, plugin_name: str) -> None:
        await self.core.writer.queue_write_operation(
            sync_mark_plugin_user_enabled_once,
            plugin_name,
        )

    async def read_provider_mutation_outcome(
        self,
        request: ProviderMutationReplayRequest,
    ) -> ProviderMutationOutcome | None:
        return await read_provider_mutation_outcome_method(self, request)

    async def get_stats_for_plugins(self, plugin_names: list[str]) -> dict[str, dict[str, int]]:
        return await compute_plugin_stats(self.core.reader, plugin_names)
