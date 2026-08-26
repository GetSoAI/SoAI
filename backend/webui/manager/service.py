"""SoAI - WebUI user and session management [backend/webui/manager/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.auth.auth_decisions import AuthenticationDecision
from core.config.clamped_numeric import read_config_nonnegative_int
from core.errors.exceptions import NotFoundError
from core.logging.protocols import StandardLogger
from core.logging.trace import get_logger
from core.network.hosts import anonymize_ip
from core.runtime.protocols import RequestProtocol
from core.serialization.json import serialize_json_compact_stable_strict
from core.system_api.request_paths import get_scope_path
from core.users.preferences import assert_supported_user_preferences
from webui.manager.authentication import evaluate_authentication_request
from webui.manager.dependencies import WebUIManagerDependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from core.users.bootstrap_state import BootstrapState

__all__ = ("WebUIManager",)

LOGGER_NAME = "SoAI.webui.manager.service"


def _initialize_webui_logger() -> StandardLogger:
    return get_logger(LOGGER_NAME)


class WebUIManager:

    def __init__(self, deps: WebUIManagerDependencies) -> None:
        self._deps = deps
        self.database_users = deps.database.database_users
        self.database_tokens = deps.database.database_tokens
        self.database_api_keys = deps.database.database_api_keys
        self.database_mcp_access_tokens = deps.database.database_mcp_access_tokens
        self.database_prompts = deps.database.database_prompts
        self.database_conversations = deps.database.database_conversations
        self.database_messages = deps.database.database_messages
        self.database_notifications = deps.database.database_notifications
        self.database_tool_calls = deps.database.database_tool_calls
        self.database_plugins = deps.database.database_plugins
        self.config = deps.config
        self.files = deps.files
        self.logger = _initialize_webui_logger()
        self.link_previews = deps.link_previews
        self.text_previews = deps.text_previews
        self.proxy_files = deps.proxy_files
        self.page_screenshots = deps.page_screenshots
        self.wallpaper = deps.wallpaper_manager
        self.openai_auth_guard = deps.auth_guards.openai_auth_guard
        self.mcp_pat_auth_guard = deps.auth_guards.mcp_pat_auth_guard
        self.webui_login_guard = deps.auth_guards.webui_login_guard
        self.identity_mutation_guard = deps.auth_guards.identity_mutation_guard
        self.key_default_ttl_days = read_config_nonnegative_int(
            self.config,
            "API.OPENAI.SECURITY.KEY_EXPIRATION.DEFAULT_TTL_DAYS",
            0,
        )
        self.key_default_rotation_days = read_config_nonnegative_int(
            self.config,
            "API.OPENAI.SECURITY.KEY_EXPIRATION.ROTATION_REMINDER_DAYS",
            0,
        )

    async def _log_auth_failure_event(
        self,
        *,
        event: str,
        request: RequestProtocol,
        reason: str,
        client_ip: str | None,
        fingerprint: str | None,
        throttled: bool,
        retry_at: int | None,
    ) -> None:
        payload = {
            "event": event,
            "reason": reason,
            "path": get_scope_path(request.scope),
            "client": anonymize_ip(client_ip) if client_ip else None,
            "fingerprint": fingerprint,
            "throttled": bool(throttled),
            "retry_at": retry_at,
        }
        self.logger.warning(
            serialize_json_compact_stable_strict(
                {
                    payload_key: payload_value
                    for payload_key, payload_value in payload.items()
                    if payload_value is not None
                },
            ),
        )

    async def has_human_users(self) -> bool:
        return await self.database_users.has_human_users()

    async def get_bootstrap_state(self) -> BootstrapState:
        return await self.database_users.get_bootstrap_state()

    async def create_user(
        self,
        username: str,
        hashed_password: str,
        is_admin: bool = False,
    ) -> JSONDict:
        return await self.database_users.create_user(username, hashed_password, is_admin)

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
        return await self.database_users.complete_licensing_wizard(
            edition=edition,
            expected_revision=expected_revision,
            current_license_fingerprint=current_license_fingerprint,
            expected_pending_document_digest=expected_pending_document_digest,
            username=username,
            language=language,
            hashed_password=hashed_password,
            completed_at_ms=completed_at_ms,
        )

    async def delete_user(self, user_id: int) -> bool:
        return await self.database_users.delete_user(user_id)

    async def authenticate_request(
        self,
        request: RequestProtocol,
        *,
        verification_secrets: tuple[str, ...],
        algorithm: str,
    ) -> AuthenticationDecision:
        return await evaluate_authentication_request(
            request,
            verification_secrets=verification_secrets,
            algorithm=algorithm,
            webui_mgr=self,
        )

    async def log_openai_auth_failure(
        self,
        request: RequestProtocol,
        reason: str,
        client_ip: str | None,
        *,
        fingerprint: str | None = None,
        throttled: bool = False,
        retry_at: int | None = None,
    ) -> None:
        await self._log_auth_failure_event(
            event="openai_auth_failure",
            request=request,
            reason=reason,
            client_ip=client_ip,
            fingerprint=fingerprint,
            throttled=throttled,
            retry_at=retry_at,
        )

    async def log_mcp_pat_auth_failure(
        self,
        request: RequestProtocol,
        reason: str,
        client_ip: str | None,
        *,
        fingerprint: str | None = None,
        throttled: bool = False,
        retry_at: int | None = None,
    ) -> None:
        await self._log_auth_failure_event(
            event="mcp_pat_auth_failure",
            request=request,
            reason=reason,
            client_ip=client_ip,
            fingerprint=fingerprint,
            throttled=throttled,
            retry_at=retry_at,
        )

    async def get_user_preferences(self, user_id: int) -> JSONDict:
        preferences = await self.database_users.get_user_preferences(user_id)
        if preferences is None:
            raise NotFoundError("User not found")
        return preferences

    async def update_user_preferences(self, user_id: int, new_prefs: JSONDict) -> JSONDict:
        assert_supported_user_preferences(new_prefs)
        preferences = await self.database_users.merge_user_preferences(user_id, new_prefs)
        if preferences is None:
            raise NotFoundError("User not found")
        return preferences

    async def reset_user_preferences(self, user_id: int) -> bool:
        reset = await self.database_users.reset_user_preferences(user_id)
        if not reset:
            raise NotFoundError("User not found")
        return True
