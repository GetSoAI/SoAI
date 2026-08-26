"""SoAI - Conversation web search payload shaping and validation [backend/features/api/routes/webui/conversation_web_search_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.conversations.conversation_mcp_extensions import (
    WEB_SEARCH_MAX_RESULTS_MAX,
    WEB_SEARCH_MAX_RESULTS_MIN,
)
from core.mcp.protocols_main import MCPSearchProtocol
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_unique_trimmed_nonempty_str_list
from features.api.runtime.errors import raise_invalid_request, raise_server_error

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_web_search_config_payload",
    "normalize_search_results",
    "read_available_providers",
    "read_default_provider",
    "read_max_results",
    "require_supported_provider_input",
)


def read_available_providers(request: Request, search_engine: MCPSearchProtocol) -> list[str]:
    providers = search_engine.list_supported_providers()
    if not isinstance(providers, list):
        raise_server_error(request, "Search engine provider list is invalid.")
    if any(
        not isinstance(provider_value, str) or not provider_value.strip()
        for provider_value in providers
    ):
        raise_server_error(request, "Search engine provider list is invalid.")
    normalized_providers = coerce_unique_trimmed_nonempty_str_list(providers)
    if not normalized_providers:
        raise_server_error(request, "Search engine provider list is invalid.")
    return normalized_providers


def read_default_provider(
    request: Request,
    search_engine: MCPSearchProtocol,
    search_config: JSONDict,
    available_providers: list[str],
) -> str:
    provider_value = search_config.get("default_provider")
    if provider_value is None:
        default_provider_value = search_engine.default_provider
        if not isinstance(default_provider_value, str):
            raise_server_error(request, "Search engine default provider is invalid.")
        default_provider = default_provider_value.strip()
        if default_provider not in available_providers:
            raise_server_error(request, "Search engine default provider is invalid.")
        return default_provider
    if not isinstance(provider_value, str):
        raise_server_error(
            request,
            "Conversation web search config 'default_provider' is invalid.",
        )
    provider = provider_value.strip()
    if not provider:
        return read_default_provider(request, search_engine, {}, available_providers)
    if provider not in available_providers:
        raise_server_error(
            request,
            "Conversation web search config 'default_provider' is invalid.",
        )
    return provider


def read_max_results(request: Request, search_config: JSONDict) -> int:
    max_results_value = search_config.get("max_results")
    if max_results_value is None:
        return 10
    if (
        isinstance(max_results_value, bool)
        or not isinstance(max_results_value, int)
        or max_results_value < WEB_SEARCH_MAX_RESULTS_MIN
        or max_results_value > WEB_SEARCH_MAX_RESULTS_MAX
    ):
        raise_server_error(request, "Conversation web search config 'max_results' is invalid.")
    return max_results_value


def require_supported_provider_input(
    request: Request,
    available_providers: list[str],
    *,
    provider: str,
    field_name: str,
) -> str:
    normalized_provider = provider.strip()
    if normalized_provider not in available_providers:
        raise_invalid_request(request, f"{field_name} is not supported.")
    return normalized_provider


def build_web_search_config_payload(
    request: Request,
    *,
    conv_id: str,
    search_engine: MCPSearchProtocol,
    search_config: JSONDict,
) -> JSONDict:
    available_providers = read_available_providers(request, search_engine)
    enabled_value = search_config.get("enabled")
    if enabled_value is None:
        enabled = False
    elif isinstance(enabled_value, bool):
        enabled = enabled_value
    else:
        raise_server_error(request, "Conversation web search config 'enabled' is invalid.")
    return {
        "conv_id": conv_id,
        "enabled": enabled,
        "default_provider": read_default_provider(
            request,
            search_engine,
            search_config,
            available_providers,
        ),
        "max_results": read_max_results(request, search_config),
        "available_providers": available_providers,
    }


def normalize_search_results(request: Request, results: list[JSONDict]) -> list[JSONDict]:
    if not isinstance(results, list):
        raise_server_error(request, "Web search response is invalid.")
    normalized_results: list[JSONDict] = []
    for result_value in results:
        result = coerce_json_dict(result_value)
        if result is None:
            raise_server_error(request, "Web search response is invalid.")
        normalized_results.append(result)
    return normalized_results
