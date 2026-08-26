"""SoAI - Canonical API route path constants [backend/core/system_api/route_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.meta.soai_v1_contract import SOAI_API_V1_PREFIX, SOAI_OPENAI_COMPAT_V1_PREFIX

__all__ = (
    "ANTHROPIC_COUNT_TOKENS_PATH",
    "ANTHROPIC_MESSAGES_PATH",
    "API_ROOT_PATH",
    "API_SURFACE_PREFIX",
    "MCP_API_PREFIX",
    "MCP_OAUTH_CALLBACK_PATH",
    "MCP_OAUTH_CALLBACK_ROUTE_PATH",
    "MCP_OAUTH_CLIENT_METADATA_PATH",
    "MCP_OAUTH_CLIENT_METADATA_ROUTE_PATH",
    "MCP_ROOT_PATH",
    "OPENAI_ANONYMOUS_COOKIE_PATH",
    "OPENAI_CHAT_COMPLETIONS_PATH",
    "OPENAI_COMPAT_PREFIX",
    "OPENAI_COMPAT_PREFIX_WITH_SLASH",
    "OPENAI_COMPLETIONS_PATH",
    "OPENAI_FILES_PATH",
    "OPENAI_OPENAPI_SCHEMA_PATH",
    "OPENAI_RESPONSES_PATH",
    "PUBLIC_API_REQUESTS",
    "SOAI_ACTIONS_PREFIX",
    "SOAI_API_OPENAPI_SCHEMA_PATH",
    "SOAI_API_PREFIX",
    "SOAI_AUTOMATIONS_PREFIX",
    "SOAI_BACKUPS_PREFIX",
    "SOAI_CONFIGS_PREFIX",
    "SOAI_FILES_PREFIX",
    "SOAI_FILE_EXPLORER_PREFIX",
    "SOAI_HARDWARE_PREFIX",
    "SOAI_MCP_PREFIX",
    "SOAI_MESSAGING_PREFIX",
    "SOAI_METRICS_PREFIX",
    "SOAI_MODELS_PREFIX",
    "SOAI_PLUGINS_PREFIX",
    "SOAI_ROUTING_PREFIX",
    "SOAI_SEARCH_PREFIX",
    "SOAI_SOFTWARE_PREFIX",
    "SOAI_SYSTEM_EVENTS_WEBSOCKET_PATH",
    "SOAI_SYSTEM_FAST_FAIL_PATHS",
    "SOAI_SYSTEM_HEALTH_PATH",
    "SOAI_SYSTEM_INFO_PATH",
    "SOAI_SYSTEM_LICENSE_PATH",
    "SOAI_SYSTEM_LIMITS_PATH",
    "SOAI_SYSTEM_PREFIX",
    "SOAI_SYSTEM_STATUS_PATH",
    "SOAI_TASKS_PREFIX",
    "SOAI_WEBUI_AUTH_LOGIN_PATH",
    "SOAI_WEBUI_PREFIX",
    "SOAI_WEBUI_WIZARD_COMPLETE_PATH",
    "SOAI_WEBUI_WIZARD_EVALUATION_TERMS_PATH",
    "SOAI_WEBUI_WIZARD_GOVERNING_DOCUMENTS_PREFIX",
    "SOAI_WEBUI_WIZARD_PERSONAL_PURCHASE_TERMS_PATH",
    "SOAI_WEBUI_WIZARD_STATUS_PATH",
)

API_ROOT_PATH: str = "/api"
API_SURFACE_PREFIX: str = "/api/"
MCP_ROOT_PATH: str = "/mcp"
MCP_API_PREFIX: str = "/mcp/"
SOAI_API_PREFIX: str = SOAI_API_V1_PREFIX
OPENAI_COMPAT_PREFIX: str = SOAI_OPENAI_COMPAT_V1_PREFIX
OPENAI_COMPAT_PREFIX_WITH_SLASH: str = "/v1/"
OPENAI_ANONYMOUS_COOKIE_PATH: str = "/v1/"
SOAI_API_OPENAPI_SCHEMA_PATH: str = "/api/v1/openapi.json"
OPENAI_OPENAPI_SCHEMA_PATH: str = "/v1/openapi.json"

SOAI_ACTIONS_PREFIX: str = "/api/v1/actions"
SOAI_AUTOMATIONS_PREFIX: str = "/api/v1/automations"
SOAI_BACKUPS_PREFIX: str = "/api/v1/backups"
SOAI_CONFIGS_PREFIX: str = "/api/v1/configs"
SOAI_FILE_EXPLORER_PREFIX: str = "/api/v1/file-explorer"
SOAI_FILES_PREFIX: str = "/api/v1/files"
SOAI_HARDWARE_PREFIX: str = "/api/v1/hardware"
SOAI_MCP_PREFIX: str = "/api/v1/mcp"
SOAI_MESSAGING_PREFIX: str = "/api/v1/messaging"
SOAI_METRICS_PREFIX: str = "/api/v1/metrics"
SOAI_MODELS_PREFIX: str = "/api/v1/models"
SOAI_PLUGINS_PREFIX: str = "/api/v1/plugins"
SOAI_ROUTING_PREFIX: str = "/api/v1/routing"
SOAI_SEARCH_PREFIX: str = SOAI_API_PREFIX
SOAI_SOFTWARE_PREFIX: str = "/api/v1/software"
SOAI_SYSTEM_PREFIX: str = "/api/v1/system"
SOAI_TASKS_PREFIX: str = "/api/v1/tasks"
SOAI_WEBUI_PREFIX: str = "/api/v1/webui"

SOAI_SYSTEM_HEALTH_PATH: str = "/api/v1/system/health"
SOAI_SYSTEM_INFO_PATH: str = "/api/v1/system/info"
SOAI_SYSTEM_LICENSE_PATH: str = "/api/v1/system/license"
SOAI_SYSTEM_LIMITS_PATH: str = "/api/v1/system/limits"
SOAI_SYSTEM_STATUS_PATH: str = "/api/v1/system/status"
SOAI_SYSTEM_EVENTS_WEBSOCKET_PATH: str = "/api/v1/system/ws"
SOAI_WEBUI_AUTH_LOGIN_PATH: str = "/api/v1/webui/auth/login"
SOAI_WEBUI_WIZARD_STATUS_PATH: str = "/api/v1/webui/wizard/status"
SOAI_WEBUI_WIZARD_COMPLETE_PATH: str = "/api/v1/webui/wizard/complete"
SOAI_WEBUI_WIZARD_EVALUATION_TERMS_PATH: str = "/api/v1/webui/wizard/licensing/evaluation-terms"
SOAI_WEBUI_WIZARD_GOVERNING_DOCUMENTS_PREFIX: str = (
    "/api/v1/webui/wizard/licensing/governing-documents/"
)
SOAI_WEBUI_WIZARD_PERSONAL_PURCHASE_TERMS_PATH: str = (
    "/api/v1/webui/wizard/licensing/personal-purchase-terms"
)
MCP_OAUTH_CLIENT_METADATA_ROUTE_PATH: str = "/oauth/client-metadata.json"
MCP_OAUTH_CALLBACK_ROUTE_PATH: str = "/oauth/callback"
MCP_OAUTH_CLIENT_METADATA_PATH: str = "/api/v1/mcp/oauth/client-metadata.json"
MCP_OAUTH_CALLBACK_PATH: str = "/api/v1/mcp/oauth/callback"

OPENAI_CHAT_COMPLETIONS_PATH: str = "/v1/chat/completions"
OPENAI_COMPLETIONS_PATH: str = "/v1/completions"
OPENAI_RESPONSES_PATH: str = "/v1/responses"
OPENAI_FILES_PATH: str = "/v1/files"
ANTHROPIC_MESSAGES_PATH: str = "/v1/messages"
ANTHROPIC_COUNT_TOKENS_PATH: str = "/v1/messages/count_tokens"

PUBLIC_API_REQUESTS: frozenset[tuple[str, str]] = frozenset(
    (
        ("GET", SOAI_SYSTEM_HEALTH_PATH),
        ("GET", SOAI_SYSTEM_INFO_PATH),
        ("GET", SOAI_SYSTEM_LIMITS_PATH),
        ("GET", SOAI_SYSTEM_LICENSE_PATH),
        ("GET", SOAI_WEBUI_WIZARD_STATUS_PATH),
        ("GET", "/api/v1/messaging/whatsapp/webhook"),
        ("GET", MCP_OAUTH_CLIENT_METADATA_PATH),
        ("GET", MCP_OAUTH_CALLBACK_PATH),
        ("POST", SOAI_WEBUI_AUTH_LOGIN_PATH),
        ("POST", "/api/v1/messaging/telegram/webhook"),
        ("POST", "/api/v1/messaging/whatsapp/webhook"),
    )
)

SOAI_SYSTEM_FAST_FAIL_PATHS: frozenset[str] = frozenset(
    (
        SOAI_SYSTEM_HEALTH_PATH,
        SOAI_SYSTEM_INFO_PATH,
        SOAI_SYSTEM_LICENSE_PATH,
        SOAI_SYSTEM_LIMITS_PATH,
        SOAI_SYSTEM_STATUS_PATH,
        SOAI_API_OPENAPI_SCHEMA_PATH,
    ),
)
