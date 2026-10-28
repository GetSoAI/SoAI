"""SoAI - Skill repository read and writer queue orchestration [backend/database/repositories/skills/repository.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.database.write_storage import DatabaseWriteStorage
from core.errors.exceptions import StateError
from core.hardware.protocols_storage import DiskSpaceReservationProviderProtocol
from core.mutations.identifiers import require_mutation_request_id
from core.skills.execution import SkillExecutionIdentity, SkillSnapshot
from core.skills.limits import MAX_MANIFEST_BYTES, skill_library_limits
from core.skills.materialization import SkillMaterializationReceipt, SkillMaterializationRequest
from core.skills.records import SkillMember, SkillPackage, StagedSkillCollection
from core.skills.selection import require_skill_id, require_skill_upload_id
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.users.user_id import require_strict_user_id
from database.core.flags import FEATURE_AUTH
from database.repositories.dependencies import DatabaseRepositoryDependencies
from database.repositories.skills.execution_reads import (
    read_execution_skill_resource,
    read_execution_skill_snapshot,
)
from database.repositories.skills.import_batches import (
    read_skill_import_batch,
    sync_import_skill_batch,
)
from database.repositories.skills.library import sync_import_skill
from database.repositories.skills.materialization import (
    sync_checkpoint_materialization,
    sync_find_materialization,
    sync_materialization_members,
    sync_read_materialization,
)
from database.repositories.skills.preview import sync_skill_read_preview
from database.repositories.skills.reads import (
    skill_read_details,
    skill_read_import_receipt,
    skill_read_library,
    skill_read_resource,
    skill_read_selection,
)
from database.repositories.skills.retention import sync_reconcile_all_skill_retention
from database.repositories.skills.selection import sync_remove_skill, sync_replace_skill_selection

__all__ = ("DatabaseSkills",)


class DatabaseSkills:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._core = deps.core
        self._config = deps.config

    def _owner(self, user_id: int) -> int:
        self._core.features.ensure_feature_enabled(FEATURE_AUTH)
        return require_strict_user_id(user_id)

    async def materialization_receipt(
        self, user_id: int, operation_key: str
    ) -> SkillMaterializationReceipt | None:
        return await self._core.writer.queue_write_operation(
            sync_find_materialization, self._owner(user_id), operation_key
        )

    async def materialization(self, user_id: int, request_id: str) -> SkillMaterializationReceipt:
        receipt = await self._core.writer.queue_write_operation(
            sync_read_materialization, require_mutation_request_id(request_id), self._owner(user_id)
        )
        if receipt is None:
            raise StateError("Skill materialization receipt is unavailable.")
        return receipt

    async def materialization_members(
        self, request: SkillMaterializationRequest
    ) -> tuple[SkillMember, ...]:
        self._owner(request.identity.user_id)
        return await self._core.writer.queue_write_operation(sync_materialization_members, request)

    async def checkpoint_materialization(
        self,
        request_id: str,
        user_id: int,
        fencing_token: int,
        expected_phase: str,
        next_phase: str,
        directory_identity: tuple[int, int] | None,
        *,
        cancelled: bool = False,
    ) -> None:
        await self._core.writer.queue_write_operation(
            sync_checkpoint_materialization,
            require_mutation_request_id(request_id),
            self._owner(user_id),
            fencing_token,
            expected_phase,
            next_phase,
            directory_identity,
            epoch_ms(),
            cancelled,
        )

    async def reconcile_retention(self) -> None:
        await self._core.writer.queue_write_operation(
            sync_reconcile_all_skill_retention, epoch_ms()
        )

    async def preview(
        self, user_id: int, conv_id: str, text: str, target_input_id: str | None = None
    ) -> SkillSnapshot:
        return await self._core.writer.queue_write_operation(
            sync_skill_read_preview, self._owner(user_id), conv_id, text, target_input_id
        )

    async def snapshot(self, user_id: int, conv_id: str, input_id: str) -> SkillSnapshot:
        return await self._core.reader.execute_read(
            read_execution_skill_snapshot, self._owner(user_id), conv_id, input_id
        )

    async def execution_resource(
        self, identity: SkillExecutionIdentity, skill_id: str, path: str, supporting: bool = False
    ) -> SkillMember:
        self._owner(identity.user_id)
        return await self._core.reader.execute_read(
            read_execution_skill_resource, identity, require_skill_id(skill_id), path, supporting
        )

    async def library(self, user_id: int) -> JSONDict:
        library = await self._core.reader.execute_read(skill_read_library, self._owner(user_id))
        library["limits"] = skill_library_limits(
            upload_bytes=resolve_upload_limit_bytes(self._config, UploadLimitType.FILE)
        )
        return library

    async def details(self, user_id: int, skill_id: str) -> JSONDict:
        return await self._core.reader.execute_read(
            skill_read_details, self._owner(user_id), require_skill_id(skill_id)
        )

    async def resource(self, user_id: int, skill_id: str, path: str) -> SkillMember:
        return await self._core.reader.execute_read(
            skill_read_resource, self._owner(user_id), require_skill_id(skill_id), path
        )

    async def import_receipt(self, user_id: int, upload_id: str) -> JSONDict | None:
        return await self._core.reader.execute_read(
            skill_read_import_receipt, self._owner(user_id), require_skill_upload_id(upload_id)
        )

    async def install(
        self,
        user_id: int,
        upload_id: str,
        package: SkillPackage,
        *,
        storage_provider: DiskSpaceReservationProviderProtocol,
    ) -> JSONDict:
        return await self._core.writer.queue_write_operation(
            sync_import_skill,
            self._owner(user_id),
            require_skill_upload_id(upload_id),
            package,
            storage=DatabaseWriteStorage(
                provider=storage_provider,
                required_bytes=4
                * (package.size_bytes + len(package.members) * 4096 + MAX_MANIFEST_BYTES * 4),
            ),
        )

    async def remove(self, user_id: int, skill_id: str) -> JSONDict:
        return await self._core.writer.queue_write_operation(
            sync_remove_skill, self._owner(user_id), require_skill_id(skill_id)
        )

    async def import_batch_receipt(self, user_id: int, upload_id: str) -> JSONDict | None:
        return await self._core.reader.execute_read(
            read_skill_import_batch, self._owner(user_id), require_skill_upload_id(upload_id)
        )

    async def install_batch(
        self,
        user_id: int,
        upload_id: str,
        collection: StagedSkillCollection,
        *,
        storage_provider: DiskSpaceReservationProviderProtocol,
    ) -> JSONDict:
        return await self._core.writer.queue_write_operation(
            sync_import_skill_batch,
            self._owner(user_id),
            require_skill_upload_id(upload_id),
            collection,
            storage=DatabaseWriteStorage(
                provider=storage_provider,
                required_bytes=4
                * sum(
                    package.size_bytes
                    + sum(resource.size_bytes for resource in package.supporting_resources)
                    + (len(package.resources) + len(package.supporting_resources)) * 4096
                    + MAX_MANIFEST_BYTES * 4
                    for package in collection.packages
                ),
            ),
        )

    async def selection(self, user_id: int, conv_id: str) -> JSONDict:
        return await self._core.reader.execute_read(
            skill_read_selection, self._owner(user_id), conv_id
        )

    async def replace_selection(
        self, user_id: int, conv_id: str, revision: int, skill_ids: tuple[str, ...]
    ) -> JSONDict:
        return await self._core.writer.queue_write_operation(
            sync_replace_skill_selection, self._owner(user_id), conv_id, revision, skill_ids
        )
