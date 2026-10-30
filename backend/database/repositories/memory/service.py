"""SoAI - Memory knowledge graph database service [backend/database/repositories/memory/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.protocols import DatabaseCoreProtocol
from database.repositories.memory.entry_mutations import (
    sync_create_entry,
    sync_delete_entry,
    sync_delete_observation,
    sync_update_entry,
)
from database.repositories.memory.management_snapshots import (
    read_managed_entry,
    read_management_library,
)
from database.repositories.memory.profile_mutations import sync_save_profile
from database.repositories.memory.read_queries import (
    read_get_entity,
    read_list_entities,
    read_search_entities,
)
from database.repositories.memory.relation_mutations import (
    sync_delete_relation,
    sync_update_relation,
)
from database.repositories.memory.write_queries import (
    sync_replace_entity_observations_for_source,
)
from database.repositories.memory.write_queries_graph_delete import sync_delete_graph
from database.repositories.memory.write_queries_graph_store import sync_store_graph
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseMemory",)


class DatabaseMemory:
    core: DatabaseCoreProtocol

    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self._event_bus = deps.event_bus

    async def store_graph(
        self,
        user_id: int,
        entities: list[JSONDict],
        observations: list[JSONDict],
        relations: list[JSONDict],
    ) -> JSONDict:
        result = await self.core.writer.queue_write_operation(
            sync_store_graph,
            user_id,
            entities,
            observations,
            relations,
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)
        return result

    async def search_entities(
        self,
        user_id: int,
        query: str,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            read_search_entities,
            user_id,
            query,
            entity_type,
            limit,
        )

    async def get_entity(self, user_id: int, name: str) -> JSONDict | None:
        return await self.core.reader.execute_read(read_get_entity, user_id, name)

    async def list_entities(self, user_id: int) -> list[JSONDict]:
        return await self.core.reader.execute_read(read_list_entities, user_id)

    async def replace_entity_observations_for_source(
        self,
        user_id: int,
        entity_name: str,
        source: str,
        contents: list[str],
        entity_type: str | None = None,
        delete_entity_if_empty: bool = False,
    ) -> None:
        normalized_entity_type = entity_type
        await self.core.writer.queue_write_operation(
            sync_replace_entity_observations_for_source,
            user_id,
            entity_name,
            source,
            contents,
            normalized_entity_type,
            delete_entity_if_empty,
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)

    async def delete_graph(
        self,
        user_id: int,
        entity_names: list[str],
        observation_ids: list[str],
        relation_ids: list[str],
    ) -> JSONDict:
        result = await self.core.writer.queue_write_operation(
            sync_delete_graph,
            user_id,
            entity_names,
            observation_ids,
            relation_ids,
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)
        return result

    async def read_library(self, user_id: int) -> JSONDict:
        return await self.core.reader.execute_read(read_management_library, user_id)

    async def read_entry(self, user_id: int, entry_id: str) -> JSONDict:
        return await self.core.reader.execute_read(read_managed_entry, user_id, entry_id)

    async def create_entry(self, user_id: int, entry_id: str, name: str, content: str) -> JSONDict:
        result = await self.core.writer.queue_write_operation(
            sync_create_entry, user_id, entry_id, name, content
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)
        return result

    async def update_entry(
        self,
        user_id: int,
        entry_id: str,
        expected_revision: str,
        name: str | None,
        observation: JSONDict | None,
    ) -> JSONDict:
        result = await self.core.writer.queue_write_operation(
            sync_update_entry, user_id, entry_id, expected_revision, name, observation
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)
        return result

    async def delete_entry(self, user_id: int, entry_id: str, expected_revision: str) -> JSONDict:
        result = await self.core.writer.queue_write_operation(
            sync_delete_entry, user_id, entry_id, expected_revision
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)
        return result

    async def delete_observation(
        self, user_id: int, entry_id: str, observation_id: str, expected_revision: str
    ) -> JSONDict:
        result = await self.core.writer.queue_write_operation(
            sync_delete_observation, user_id, entry_id, observation_id, expected_revision
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)
        return result

    async def update_relation(
        self,
        user_id: int,
        entry_id: str,
        relation_id: str,
        expected_revision: str,
        from_entity_id: str,
        to_entity_id: str,
        relation_type: str,
    ) -> JSONDict:
        result = await self.core.writer.queue_write_operation(
            sync_update_relation,
            user_id,
            entry_id,
            relation_id,
            expected_revision,
            from_entity_id,
            to_entity_id,
            relation_type,
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)
        return result

    async def delete_relation(
        self, user_id: int, entry_id: str, relation_id: str, expected_revision: str
    ) -> JSONDict:
        result = await self.core.writer.queue_write_operation(
            sync_delete_relation, user_id, entry_id, relation_id, expected_revision
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)
        return result

    async def save_profile(
        self, user_id: int, payload: JSONDict, expected_revision: str | None = None
    ) -> JSONDict:
        result = await self.core.writer.queue_write_operation(
            sync_save_profile, user_id, payload, expected_revision
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)
        return result
