"""SoAI - Memory knowledge graph database service [backend/database/repositories/memory/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.protocols import DatabaseCoreProtocol
from database.repositories.memory.read_queries import (
    read_get_entity,
    read_list_entities,
    read_search_entities,
)
from database.repositories.memory.write_queries import (
    sync_replace_entity_observations_for_source,
)
from database.repositories.memory.write_queries_graph_delete import sync_delete_graph
from database.repositories.memory.write_queries_graph_store import sync_store_graph

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseMemory",)


class DatabaseMemory:
    core: DatabaseCoreProtocol

    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def store_graph(
        self,
        user_id: int,
        entities: list[JSONDict],
        observations: list[JSONDict],
        relations: list[JSONDict],
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_store_graph,
            user_id,
            entities,
            observations,
            relations,
        )

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

    async def delete_graph(
        self,
        user_id: int,
        entity_names: list[str],
        observation_ids: list[str],
        relation_ids: list[str],
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_delete_graph,
            user_id,
            entity_names,
            observation_ids,
            relation_ids,
        )
