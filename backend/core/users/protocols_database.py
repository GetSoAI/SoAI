"""SoAI - WebUI database user protocol definitions [backend/core/users/protocols_database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from core.users.bootstrap_state import BootstrapState

__all__ = ("DatabaseUsersProtocol", "UserLoginRecord")


@dataclass(frozen=True, slots=True)
class UserLoginRecord:
    user_id: int
    username: str
    hashed_password: str = field(repr=False)
    password_revision: int


class DatabaseUsersProtocol(Protocol):
    async def get_bootstrap_state(self) -> BootstrapState: ...
    async def has_human_users(self) -> bool: ...
    async def count_human_admins(self) -> int: ...
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
    ) -> JSONDict: ...
    async def get_human_user_by_id(self, user_id: int) -> JSONDict | None: ...
    async def get_human_user_by_username(self, username: str) -> JSONDict | None: ...
    async def get_human_login_record_by_username(
        self,
        username: str,
    ) -> UserLoginRecord | None: ...
    async def get_account_by_id(self, user_id: int) -> JSONDict | None: ...
    async def create_user(
        self,
        username: str,
        hashed_password: str,
        is_admin: bool = False,
    ) -> JSONDict: ...
    async def list_human_users(self) -> list[JSONDict]: ...
    async def list_all_accounts(self) -> list[JSONDict]: ...
    async def update_user_password(self, username: str, new_hashed_password: str) -> bool: ...
    async def update_user_role(self, user_id: int, is_admin: bool) -> JSONDict | None: ...
    async def update_user_workspace_path(
        self,
        user_id: int,
        workspace_path: str | None,
        workspace_real_path: str,
    ) -> JSONDict | None: ...
    async def delete_user(self, user_id: int) -> bool: ...
    async def get_user_preferences(self, user_id: int) -> JSONDict | None: ...
    async def merge_user_preferences(self, user_id: int, patch: JSONDict) -> JSONDict | None: ...
    async def set_default_assistant_name(
        self,
        user_id: int,
        assistant_name: str | None,
    ) -> JSONDict | None: ...
    async def clear_tool_approval_permissions(self, user_id: int) -> JSONDict | None: ...
    async def reset_user_preferences(self, user_id: int) -> bool: ...
