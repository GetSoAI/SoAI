"""SoAI - Database repository for JWT revocation tokens [backend/database/repositories/users/tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sqlite3
from typing import TYPE_CHECKING

from core.auth.protocols_database_tokens import (
    SessionLineageRevocationResult,
    SessionRotationRecoveryState,
    TokenAuthReadState,
)
from core.auth.webui_sessions import (
    WEBUI_SESSION_TOUCH_INTERVAL_MS,
    WebuiSessionDescriptor,
    WebuiSessionRegistrationResult,
)
from core.errors.exceptions import DatabaseError
from core.timing.epoch import epoch_ms
from core.users.user_id import require_strict_user_id
from database.core.flags import FEATURE_AUTH
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)
from database.repositories.users.webui_identity_maintenance import (
    sync_prune_expired_session_lineage_state,
)
from database.repositories.users.webui_session_lineage import (
    sync_recover_session_rotation,
    sync_revoke_all_user_sessions,
    sync_revoke_owned_session_lineage,
    sync_revoke_session_lineage,
)
from database.repositories.users.webui_session_queries import (
    query_active_admin_session_device_count,
    query_active_session_descriptor,
    query_active_sessions,
    query_session_jti_exists,
    query_token_auth_state,
)
from database.repositories.users.webui_session_registration import (
    raise_classified_webui_session_registration_error,
    sync_register_webui_session,
    sync_rename_android_webui_session,
    sync_touch_webui_session,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseTokens",)


class DatabaseTokens:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self.core = deps.core
        self.config = deps.config
        self.fernet = deps.fernet
        self._session_touch_lock = asyncio.Lock()
        self._session_touch_deadlines: dict[str, int] = {}

    def _set_session_touch_deadline(self, jti: str, deadline_ms: int) -> None:
        expired_jtis = [
            cached_jti
            for cached_jti, cached_deadline_ms in self._session_touch_deadlines.items()
            if cached_deadline_ms <= deadline_ms - WEBUI_SESSION_TOUCH_INTERVAL_MS
        ]
        for expired_jti in expired_jtis:
            self._session_touch_deadlines.pop(expired_jti, None)
        self._session_touch_deadlines[jti] = deadline_ms

    def _remove_session_touch_deadlines(self, revoked_jtis: tuple[str, ...]) -> None:
        for revoked_jti in revoked_jtis:
            self._session_touch_deadlines.pop(revoked_jti, None)

    async def _finalize_session_revocation(self, revoked_jtis: tuple[str, ...]) -> None:
        if not revoked_jtis:
            return
        async with self._session_touch_lock:
            self._remove_session_touch_deadlines(revoked_jtis)
        notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)

    def _sync_prune_expired_webui_session_state(self, conn: sqlite3.Connection) -> None:
        sync_prune_expired_session_lineage_state(conn, epoch_ms())

    async def prune_expired_webui_session_state(self) -> None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        await self.core.writer.queue_write_operation(self._sync_prune_expired_webui_session_state)

    async def count_active_admin_session_devices(self) -> int:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        observed_at_ms = epoch_ms()
        return await self.core.reader.execute_read(
            lambda database: query_active_admin_session_device_count(database, observed_at_ms)
        )

    async def read_token_auth_state(
        self,
        *,
        jti: str | None,
        user_id: int | None,
        username: str | None,
    ) -> TokenAuthReadState:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        observed_at_ms = epoch_ms()
        return await self.core.reader.execute_read(
            lambda database: query_token_auth_state(
                database,
                jti=jti,
                user_id=user_id,
                username=username or "",
                observed_at_ms=observed_at_ms,
            )
        )

    async def session_jti_exists(self, *, jti: str) -> bool:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await self.core.reader.execute_read(
            lambda database: query_session_jti_exists(database, jti)
        )

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
    ) -> WebuiSessionRegistrationResult | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        try:
            result = await self.core.writer.queue_write_operation(
                sync_register_webui_session,
                jti,
                require_strict_user_id(expected_user_id),
                username,
                expected_password_revision,
                descriptor,
                issued_at_ms,
                expires_at_ms,
            )
        except (sqlite3.IntegrityError, DatabaseError) as exception:
            raise_classified_webui_session_registration_error(exception)
        if isinstance(result, WebuiSessionRegistrationResult):
            async with self._session_touch_lock:
                self._remove_session_touch_deadlines(result.revoked_jtis)
                self._set_session_touch_deadline(
                    jti,
                    issued_at_ms + WEBUI_SESSION_TOUCH_INTERVAL_MS,
                )
            return result
        return None

    async def list_active_sessions(
        self,
        *,
        user_id: int,
        current_jti: str,
    ) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        resolved_user_id = require_strict_user_id(user_id)
        observed_at_ms = epoch_ms()

        return await self.core.reader.execute_read(
            lambda database: query_active_sessions(
                database,
                resolved_user_id,
                current_jti,
                observed_at_ms,
            )
        )

    async def read_active_session_descriptor(
        self,
        *,
        user_id: int,
        jti: str,
    ) -> WebuiSessionDescriptor | None:
        resolved_user_id = require_strict_user_id(user_id)
        observed_at_ms = epoch_ms()

        return await self.core.reader.execute_read(
            lambda database: query_active_session_descriptor(
                database,
                resolved_user_id,
                jti,
                observed_at_ms,
            )
        )

    async def touch_session(self, *, jti: str, observed_at_ms: int) -> bool:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        async with self._session_touch_lock:
            deadline = self._session_touch_deadlines.get(jti, 0)
            if observed_at_ms < deadline:
                return False
            touched = await self.core.writer.queue_write_operation(
                sync_touch_webui_session,
                jti,
                observed_at_ms,
            )
            self._set_session_touch_deadline(
                jti,
                observed_at_ms + WEBUI_SESSION_TOUCH_INTERVAL_MS,
            )
            return bool(touched)

    async def revoke_owned_session_lineage(
        self,
        *,
        user_id: int,
        source_jti: str,
        deadline_monotonic: float,
    ) -> SessionLineageRevocationResult | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        result = await self.core.writer.queue_write_operation(
            sync_revoke_owned_session_lineage,
            require_strict_user_id(user_id),
            source_jti,
            deadline_monotonic,
        )
        if result is not None:
            await self._finalize_session_revocation(result.revoked_jtis)
        return result

    async def revoke_all_user_sessions(
        self,
        *,
        user_id: int,
        deadline_monotonic: float,
    ) -> SessionLineageRevocationResult:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        result = await self.core.writer.queue_write_operation(
            sync_revoke_all_user_sessions,
            require_strict_user_id(user_id),
            deadline_monotonic,
        )
        await self._finalize_session_revocation(result.revoked_jtis)
        return result

    async def recover_session_rotation(
        self,
        *,
        source_jti: str,
        user_id: int,
        source_password_revision: int,
        source_issued_at_ms: int,
        source_expires_at_ms: int,
        observed_at_ms: int,
    ) -> SessionRotationRecoveryState:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await self.core.writer.queue_write_operation(
            sync_recover_session_rotation,
            source_jti,
            require_strict_user_id(user_id),
            source_password_revision,
            source_issued_at_ms,
            source_expires_at_ms,
            observed_at_ms,
        )

    async def revoke_session_lineage(
        self,
        *,
        user_id: int,
        source_jti: str,
        admitted_at_ms: int,
        deadline_monotonic: float,
    ) -> SessionLineageRevocationResult:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        result = await self.core.writer.queue_write_operation(
            sync_revoke_session_lineage,
            require_strict_user_id(user_id),
            source_jti,
            admitted_at_ms,
            deadline_monotonic,
        )
        await self._finalize_session_revocation(result.revoked_jtis)
        return result

    async def rename_android_session(
        self,
        *,
        user_id: int,
        jti: str,
        device_id: str,
        device_label: str,
    ) -> bool:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        renamed = await self.core.writer.queue_write_operation(
            sync_rename_android_webui_session,
            require_strict_user_id(user_id),
            jti,
            device_id,
            device_label,
            epoch_ms(),
        )
        return bool(renamed)
