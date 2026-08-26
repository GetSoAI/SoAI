"""SoAI - WebUI database token protocol definitions [backend/core/auth/protocols_database_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from core.auth.webui_sessions import (
    WebuiSessionDescriptor,
    WebuiSessionRegistrationResult,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "DatabaseTokensProtocol",
    "SessionLineageRevocationResult",
    "SessionRotationRecoveryState",
    "TokenAuthReadState",
)


@dataclass(frozen=True, slots=True)
class TokenAuthReadState:
    status: Literal["active", "session_revoked", "session_rotated"]
    user: JSONDict | None
    replacement_jti: str | None = None
    replacement_issued_at_ms: int | None = None
    replacement_expires_at_ms: int | None = None
    replacement_password_revision: int | None = None
    recoverable_until_ms: int | None = None
    operation_id: str | None = None


@dataclass(frozen=True, slots=True)
class SessionRotationRecoveryState:
    status: Literal["recovered", "terminal"]
    user: JSONDict | None = None
    replacement_jti: str | None = None
    replacement_issued_at_ms: int | None = None
    replacement_expires_at_ms: int | None = None
    replacement_password_revision: int | None = None
    operation_id: str | None = None


@dataclass(frozen=True, slots=True)
class SessionLineageRevocationResult:
    username: str
    revoked_jtis: tuple[str, ...]


class DatabaseTokensProtocol(Protocol):
    async def prune_expired_webui_session_state(self) -> None: ...
    async def count_active_admin_session_devices(self) -> int: ...
    async def read_token_auth_state(
        self,
        *,
        jti: str | None,
        user_id: int | None,
        username: str | None,
    ) -> TokenAuthReadState: ...
    async def session_jti_exists(self, *, jti: str) -> bool: ...
    async def register_session(
        self,
        *,
        jti: str,
        expected_user_id: int,
        username: str,
        expected_password_revision: int,
        descriptor: WebuiSessionDescriptor,
        issued_at_ms: int,
        expires_at_ms: int,
    ) -> WebuiSessionRegistrationResult | None: ...
    async def list_active_sessions(
        self,
        *,
        user_id: int,
        current_jti: str,
    ) -> list[JSONDict]: ...
    async def read_active_session_descriptor(
        self,
        *,
        user_id: int,
        jti: str,
    ) -> WebuiSessionDescriptor | None: ...
    async def touch_session(self, *, jti: str, observed_at_ms: int) -> bool: ...
    async def revoke_owned_session_lineage(
        self,
        *,
        user_id: int,
        source_jti: str,
        deadline_monotonic: float,
    ) -> SessionLineageRevocationResult | None: ...
    async def revoke_all_user_sessions(
        self,
        *,
        user_id: int,
        deadline_monotonic: float,
    ) -> SessionLineageRevocationResult: ...
    async def recover_session_rotation(
        self,
        *,
        source_jti: str,
        user_id: int,
        source_password_revision: int,
        source_issued_at_ms: int,
        source_expires_at_ms: int,
        observed_at_ms: int,
    ) -> SessionRotationRecoveryState: ...
    async def revoke_session_lineage(
        self,
        *,
        user_id: int,
        source_jti: str,
        admitted_at_ms: int,
        deadline_monotonic: float,
    ) -> SessionLineageRevocationResult: ...
    async def rename_android_session(
        self,
        *,
        user_id: int,
        jti: str,
        device_id: str,
        device_label: str,
    ) -> bool: ...
