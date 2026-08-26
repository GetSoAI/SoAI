"""SoAI - WebUI manager protocol definitions [backend/core/webui_manager/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from core.auth.auth_decisions import AuthenticationDecision
from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
from core.auth.protocols_database_mcp_access_tokens import (
    DatabaseMcpAccessTokensProtocol,
)
from core.auth.protocols_database_tokens import DatabaseTokensProtocol
from core.config.protocols import ConfigProtocol
from core.conversations.protocols_database_conversation_records import (
    DatabaseConversationsProtocol,
)
from core.conversations.protocols_database_conversations import (
    DatabaseMessagesProtocol,
)
from core.di.validation import require_dependencies
from core.media_preview.media_preview_models import (
    MediaLinkPreview,
    ProxyFile,
    TextPreview,
)
from core.notifications.protocols_database import DatabaseNotificationsProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.prompts.protocols_database import DatabasePromptsProtocol
from core.runtime.protocols import RequestProtocol
from core.tool_calls.protocols import DatabaseToolCallsProtocol
from core.users.protocols_database import DatabaseUsersProtocol
from core.wallpaper.protocols import AuthGuardProtocol, WallpaperManagerProtocol

if TYPE_CHECKING:
    import httpx2

    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict
    from core.users.bootstrap_state import BootstrapState

__all__ = (
    "WebUIAuthContextProtocol",
    "WebUILinkPreviewScreenshotCapturerProtocol",
    "WebUILinkPreviewServiceProtocol",
    "WebUIManagerDatabaseDependencies",
    "WebUIManagerProtocol",
    "WebUIPageScreenshotServiceProtocol",
    "WebUIProxyFileServiceProtocol",
    "WebUITextPreviewServiceProtocol",
)


@dataclass(frozen=True, slots=True)
class WebUIManagerDatabaseDependencies:
    database_users: DatabaseUsersProtocol
    database_tokens: DatabaseTokensProtocol
    database_api_keys: DatabaseAPIKeysProtocol
    database_mcp_access_tokens: DatabaseMcpAccessTokensProtocol
    database_prompts: DatabasePromptsProtocol
    database_conversations: DatabaseConversationsProtocol
    database_messages: DatabaseMessagesProtocol
    database_notifications: DatabaseNotificationsProtocol
    database_tool_calls: DatabaseToolCallsProtocol
    database_plugins: DatabasePluginsProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="WebUIManagerDatabaseDependencies",
            database_api_keys=self.database_api_keys,
            database_conversations=self.database_conversations,
            database_messages=self.database_messages,
            database_mcp_access_tokens=self.database_mcp_access_tokens,
            database_notifications=self.database_notifications,
            database_plugins=self.database_plugins,
            database_prompts=self.database_prompts,
            database_tokens=self.database_tokens,
            database_tool_calls=self.database_tool_calls,
            database_users=self.database_users,
        )


class WebUIAuthContextProtocol(Protocol):

    database_users: DatabaseUsersProtocol
    database_tokens: DatabaseTokensProtocol
    database_api_keys: DatabaseAPIKeysProtocol
    database_mcp_access_tokens: DatabaseMcpAccessTokensProtocol

    async def has_human_users(self) -> bool: ...
    async def get_bootstrap_state(self) -> BootstrapState: ...

    async def log_openai_auth_failure(
        self,
        request: RequestProtocol,
        reason: str,
        client_ip: str | None,
        *,
        fingerprint: str | None = None,
        throttled: bool = False,
        retry_at: int | None = None,
    ) -> None: ...

    async def log_mcp_pat_auth_failure(
        self,
        request: RequestProtocol,
        reason: str,
        client_ip: str | None,
        *,
        fingerprint: str | None = None,
        throttled: bool = False,
        retry_at: int | None = None,
    ) -> None: ...

    @property
    def openai_auth_guard(self) -> AuthGuardProtocol: ...

    @property
    def mcp_pat_auth_guard(self) -> AuthGuardProtocol: ...


class WebUIManagerProtocol(WebUIAuthContextProtocol, Protocol):

    wallpaper: WallpaperManagerProtocol
    link_previews: WebUILinkPreviewServiceProtocol
    text_previews: WebUITextPreviewServiceProtocol
    proxy_files: WebUIProxyFileServiceProtocol
    page_screenshots: WebUIPageScreenshotServiceProtocol
    webui_login_guard: AuthGuardProtocol
    identity_mutation_guard: AuthGuardProtocol
    database_users: DatabaseUsersProtocol
    database_tokens: DatabaseTokensProtocol
    database_api_keys: DatabaseAPIKeysProtocol
    database_mcp_access_tokens: DatabaseMcpAccessTokensProtocol
    database_prompts: DatabasePromptsProtocol
    database_conversations: DatabaseConversationsProtocol
    database_messages: DatabaseMessagesProtocol
    database_notifications: DatabaseNotificationsProtocol
    database_tool_calls: DatabaseToolCallsProtocol
    database_plugins: DatabasePluginsProtocol
    key_default_ttl_days: int
    key_default_rotation_days: int

    @property
    def config(self) -> ConfigProtocol: ...

    async def create_user(
        self,
        username: str,
        hashed_password: str,
        is_admin: bool = False,
    ) -> JSONDict: ...
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
    async def delete_user(self, user_id: int) -> bool: ...

    async def authenticate_request(
        self,
        request: RequestProtocol,
        *,
        verification_secrets: tuple[str, ...],
        algorithm: str,
    ) -> AuthenticationDecision: ...

    async def get_user_preferences(self, user_id: int) -> JSONDict: ...

    async def update_user_preferences(self, user_id: int, new_prefs: JSONDict) -> JSONDict: ...

    async def reset_user_preferences(self, user_id: int) -> bool: ...


class WebUILinkPreviewServiceProtocol(Protocol):
    async def get_link_preview(
        self,
        http_client: httpx2.AsyncClient,
        runtime_flags: RuntimeFlagsViewProtocol,
        source_url: str,
    ) -> MediaLinkPreview: ...


class WebUITextPreviewServiceProtocol(Protocol):
    async def get_text_preview(
        self,
        http_client: httpx2.AsyncClient,
        runtime_flags: RuntimeFlagsViewProtocol,
        source_url: str,
    ) -> TextPreview: ...


class WebUIProxyFileServiceProtocol(Protocol):
    async def prepare_proxy_file(
        self,
        http_client: httpx2.AsyncClient,
        runtime_flags: RuntimeFlagsViewProtocol,
        source_url: str,
        *,
        download: bool,
    ) -> ProxyFile: ...


class WebUILinkPreviewScreenshotCapturerProtocol(Protocol):
    async def capture_link_preview_screenshot_png(
        self,
        runtime_flags: RuntimeFlagsViewProtocol,
        *,
        url: str,
        source_html: str | None = None,
    ) -> tuple[bytes | None, str | None]: ...


class WebUIPageScreenshotServiceProtocol(Protocol):
    async def store_page_screenshot_png(
        self,
        runtime_flags: RuntimeFlagsViewProtocol,
        *,
        url: str,
        image_bytes_png: bytes,
    ) -> None: ...

    async def prepare_page_screenshot_file(
        self,
        runtime_flags: RuntimeFlagsViewProtocol,
        source_url: str,
    ) -> ProxyFile: ...
