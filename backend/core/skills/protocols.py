"""SoAI - Skill persistence subsystem contracts [backend/core/skills/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable
from typing import Protocol

from core.hardware.protocols_storage import DiskSpaceReservationProviderProtocol
from core.skills.execution import SkillExecutionContext, SkillExecutionIdentity, SkillSnapshot
from core.skills.materialization import SkillMaterializationReceipt, SkillMaterializationRequest
from core.skills.records import SkillMember, SkillPackage, StagedSkillCollection
from core.types.json import JSONDict

__all__ = ("SkillRepositoryProtocol", "SkillActivationCallback")


class SkillActivationCallback(Protocol):
    def __call__(
        self, skill_id: str, call_id: str, result: JSONDict, arguments: str | None = None
    ) -> Awaitable[SkillExecutionContext]: ...


class SkillRepositoryProtocol(Protocol):
    async def materialization_receipt(
        self, user_id: int, operation_key: str
    ) -> SkillMaterializationReceipt | None: ...
    async def materialization(
        self, user_id: int, request_id: str
    ) -> SkillMaterializationReceipt: ...
    async def materialization_members(
        self, request: SkillMaterializationRequest
    ) -> tuple[SkillMember, ...]: ...
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
    ) -> None: ...
    async def reconcile_retention(self) -> None: ...
    async def execution_resource(
        self, identity: SkillExecutionIdentity, skill_id: str, path: str, supporting: bool = False
    ) -> SkillMember: ...
    async def preview(
        self, user_id: int, conv_id: str, text: str, target_input_id: str | None = None
    ) -> SkillSnapshot: ...
    async def snapshot(self, user_id: int, conv_id: str, input_id: str) -> SkillSnapshot: ...
    async def library(self, user_id: int) -> JSONDict: ...
    async def details(self, user_id: int, skill_id: str) -> JSONDict: ...
    async def resource(self, user_id: int, skill_id: str, path: str) -> SkillMember: ...
    async def import_receipt(self, user_id: int, upload_id: str) -> JSONDict | None: ...
    async def import_batch_receipt(self, user_id: int, upload_id: str) -> JSONDict | None: ...
    async def install_batch(
        self,
        user_id: int,
        upload_id: str,
        collection: StagedSkillCollection,
        *,
        storage_provider: DiskSpaceReservationProviderProtocol,
    ) -> JSONDict: ...
    async def install(
        self,
        user_id: int,
        upload_id: str,
        package: SkillPackage,
        *,
        storage_provider: DiskSpaceReservationProviderProtocol,
    ) -> JSONDict: ...
    async def remove(self, user_id: int, skill_id: str) -> JSONDict: ...
    async def selection(self, user_id: int, conv_id: str) -> JSONDict: ...
    async def replace_selection(
        self, user_id: int, conv_id: str, revision: int, skill_ids: tuple[str, ...]
    ) -> JSONDict: ...
