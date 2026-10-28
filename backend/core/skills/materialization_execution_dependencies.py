"""SoAI - Skill materialization execution dependencies [backend/core/skills/materialization_execution_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.conversations.protocols_database_conversation_records import DatabaseConversationsProtocol
from core.database.protocols_tasks import DatabaseTasksProtocol
from core.di.validation import require_dependencies
from core.files.protocols import FilesPathResolverProtocol
from core.hardware.protocols_storage import DiskSpaceReservationProviderProtocol
from core.skills.protocols import SkillRepositoryProtocol
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)
from core.users.protocols_database import DatabaseUsersProtocol

__all__ = ("SkillMaterializationServiceDependencies",)


@dataclass(frozen=True, slots=True)
class SkillMaterializationServiceDependencies:
    skills: SkillRepositoryProtocol
    tasks: DatabaseTasksProtocol
    registry: TaskRegistryProtocol
    users: DatabaseUsersProtocol
    conversations: DatabaseConversationsProtocol
    files: FilesPathResolverProtocol
    storage: DiskSpaceReservationProviderProtocol
    token_collection: TokenCollectionProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    plugin_directory: str

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SkillMaterializationServiceDependencies",
            skills=self.skills,
            tasks=self.tasks,
            registry=self.registry,
            users=self.users,
            conversations=self.conversations,
            files=self.files,
            storage=self.storage,
            token_collection=self.token_collection,
            cancellation_history=self.cancellation_history,
            cancellation_event_bus=self.cancellation_event_bus,
            plugin_directory=self.plugin_directory,
        )
