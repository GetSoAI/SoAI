"""SoAI - User repository with CRUD, auth, and preferences [backend/database/repositories/users/users.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import aiosqlite

from core.users.account_types import HUMAN_ACCOUNT_TYPE
from core.users.bootstrap_state import BootstrapState
from core.users.username import require_canonical_username
from database.core.flags import FEATURE_AUTH
from database.core.query_execution import query_one_to_dict
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)
from database.repositories.users.user_count_queries import (
    query_bootstrap_state,
    query_human_admin_count,
    query_human_user_count,
)
from database.repositories.users.user_listing_queries import query_all_accounts, query_human_users
from database.repositories.users.user_login_row import normalize_user_login_row
from database.repositories.users.user_password_updates import (
    sync_update_user_password,
)
from database.repositories.users.user_preference_mutations import (
    read_user_preferences_query,
    sync_clear_tool_approval_permissions,
    sync_merge_user_preferences,
    sync_set_default_assistant_name,
)
from database.repositories.users.user_row_normalization import normalize_user_row
from database.repositories.users.user_sync_creation import sync_create_user
from database.repositories.users.user_sync_updates import (
    sync_clear_user_preferences,
    sync_delete_user,
    sync_update_user_role,
    sync_update_user_workspace_path,
)
from database.repositories.users.wizard_completion import sync_complete_licensing_wizard

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from core.users.protocols_database import UserLoginRecord
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseUsers",)


class DatabaseUsers:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self.core = deps.core
        self.config = deps.config
        self.fernet = deps.fernet
        self._user_presence_lock = asyncio.Lock()
        self._has_users_cache: bool | None = None
        self._bootstrap_state_cache: BootstrapState | None = None

    async def create_user(
        self,
        username: str,
        hashed_password: str,
        is_admin: bool = False,
    ) -> JSONDict:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        async with self._user_presence_lock:
            result = await self.core.writer.queue_write_operation(
                sync_create_user,
                username,
                hashed_password,
                is_admin,
            )
            if isinstance(result, dict):
                self._has_users_cache = True
                self._bootstrap_state_cache = None
        if isinstance(result, dict):
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result

    async def complete_licensing_wizard(
        self,
        *,
        edition: str,
        expected_revision: int,
        current_license_fingerprint: str,
        expected_pending_document_digest: str | None,
        username: str,
        language: str,
        hashed_password: str,
        completed_at_ms: int,
    ) -> JSONDict:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        async with self._user_presence_lock:
            result = await self.core.writer.queue_write_operation(
                sync_complete_licensing_wizard,
                edition,
                expected_revision,
                current_license_fingerprint,
                expected_pending_document_digest,
                username,
                language,
                hashed_password,
                completed_at_ms,
            )
            self._has_users_cache = True
            self._bootstrap_state_cache = BootstrapState.COMPLETE
        notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result

    async def get_human_user_by_username(self, username: str) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        normalized_username = require_canonical_username(username)

        async def _query(
            database: aiosqlite.Connection,
        ) -> JSONDict | None:
            row = await query_one_to_dict(
                database,
                "SELECT * FROM webui_users WHERE username = ? AND account_type = ?",
                (normalized_username, HUMAN_ACCOUNT_TYPE),
            )
            return normalize_user_row(row)

        return await self.core.reader.execute_read(_query)

    async def get_human_login_record_by_username(
        self,
        username: str,
    ) -> UserLoginRecord | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        normalized_username = require_canonical_username(username)

        async def _query(
            database: aiosqlite.Connection,
        ) -> UserLoginRecord | None:
            row = await query_one_to_dict(
                database,
                """
                SELECT id, username, hashed_password, password_revision
                FROM webui_users
                WHERE username = ? AND account_type = ?
                """,
                (normalized_username, HUMAN_ACCOUNT_TYPE),
            )
            return normalize_user_login_row(row)

        return await self.core.reader.execute_read(_query)

    async def get_human_user_by_id(self, user_id: int) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)

        async def _query(
            database: aiosqlite.Connection,
        ) -> JSONDict | None:
            row = await query_one_to_dict(
                database,
                "SELECT * FROM webui_users WHERE id = ? AND account_type = ?",
                (user_id, HUMAN_ACCOUNT_TYPE),
            )
            return normalize_user_row(row)

        return await self.core.reader.execute_read(_query)

    async def get_account_by_id(self, user_id: int) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)

        async def _query(database: aiosqlite.Connection) -> JSONDict | None:
            row = await query_one_to_dict(
                database,
                "SELECT * FROM webui_users WHERE id = ?",
                (user_id,),
            )
            return normalize_user_row(row)

        return await self.core.reader.execute_read(_query)

    async def update_user_password(self, username: str, new_hashed_password: str) -> bool:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        updated = await self.core.writer.queue_write_operation(
            sync_update_user_password,
            username,
            new_hashed_password,
        )
        if updated:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return bool(updated)

    async def update_user_role(self, user_id: int, is_admin: bool) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        updated_user = await self.core.writer.queue_write_operation(
            sync_update_user_role,
            user_id,
            is_admin,
        )
        if isinstance(updated_user, dict):
            async with self._user_presence_lock:
                self._bootstrap_state_cache = None
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return updated_user

    async def update_user_workspace_path(
        self,
        user_id: int,
        workspace_path: str | None,
        workspace_real_path: str,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await self.core.writer.queue_write_operation(
            sync_update_user_workspace_path,
            user_id,
            workspace_path,
            workspace_real_path,
        )

    async def delete_user(self, user_id: int) -> bool:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        async with self._user_presence_lock:
            deleted = await self.core.writer.queue_write_operation(
                sync_delete_user,
                user_id,
            )
            if deleted:
                self._has_users_cache = None
                self._bootstrap_state_cache = None
        if deleted:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return bool(deleted)

    async def has_human_users(self) -> bool:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        async with self._user_presence_lock:
            if self._has_users_cache is None:
                self._has_users_cache = await query_human_user_count(self.core) > 0
            return self._has_users_cache

    async def get_bootstrap_state(self) -> BootstrapState:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        async with self._user_presence_lock:
            if self._bootstrap_state_cache is None:
                self._bootstrap_state_cache = await query_bootstrap_state(self.core)
            return self._bootstrap_state_cache

    async def count_human_admins(self) -> int:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await query_human_admin_count(self.core)

    async def get_user_preferences(self, user_id: int) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await self.core.reader.execute_read(
            read_user_preferences_query,
            user_id=user_id,
        )

    async def merge_user_preferences(self, user_id: int, patch: JSONDict) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await self.core.writer.queue_write_operation(
            sync_merge_user_preferences,
            user_id,
            patch,
        )

    async def set_default_assistant_name(
        self,
        user_id: int,
        assistant_name: str | None,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await self.core.writer.queue_write_operation(
            sync_set_default_assistant_name,
            user_id,
            assistant_name,
        )

    async def clear_tool_approval_permissions(self, user_id: int) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await self.core.writer.queue_write_operation(
            sync_clear_tool_approval_permissions,
            user_id,
        )

    async def reset_user_preferences(self, user_id: int) -> bool:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await self.core.writer.queue_write_operation(
            sync_clear_user_preferences,
            user_id,
        )

    async def list_human_users(self) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await self.core.reader.execute_read(query_human_users)

    async def list_all_accounts(self) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await self.core.reader.execute_read(query_all_accounts)
