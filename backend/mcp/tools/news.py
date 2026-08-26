"""SoAI - MCP news tool implementation [backend/mcp/tools/news.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Never

from core.config.numeric_lenient import (
    coerce_lenient_bounded_float,
    coerce_lenient_positive_int,
)
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import RateLimitError
from core.errors.external_service_exception import ExternalServiceError
from core.logging.trace import get_logger
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.configured_http_endpoint import (
    ConfiguredEndpointNetworkTarget,
    ConfiguredEndpointSpec,
    resolve_configured_endpoint_from_spec,
)
from mcp.tools.error import MCPToolError
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.news_http import fetch_news_provider_payload
from mcp.tools.news_payload import (
    NEWS_SEARCH_MODE_FULLTEXT_COUNTRY,
    NEWS_SEARCH_MODE_HEADLINE_SUMMARY_GLOBAL,
    build_news_result_payload,
)
from mcp.tools.news_query import (
    NewsRequest,
    build_news_cache_key,
    build_news_request,
    build_news_url,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_news",)

_ALLOWED_KEYS: frozenset[str] = frozenset({"query", "language", "country", "max_results"})
_DEFAULT_BASE_URL = "https://api.gdeltproject.org/api/v2/doc"
_CONFIG_PREFIX = "TOOLS.MCP.NEWS"
_LOGGER_NAME = "SoAI.mcp.tools.news"
OPERATION_GAL_SEARCH = "mcp.tools.news.gal_search"


def _raise_news_provider_error(exception: RateLimitError | ExternalServiceError) -> Never:
    if isinstance(exception, RateLimitError):
        raise MCPToolError(
            -32603,
            "News provider rate limit was reached. Retry later.",
        ) from exception
    raise MCPToolError(-32603, exception.message) from exception


async def _resolve_news_network_target(
    utility_tools: MCPUtilityToolsProtocol,
) -> ConfiguredEndpointNetworkTarget:
    return await resolve_configured_endpoint_from_spec(
        config=utility_tools.config,
        runtime_flags=utility_tools.runtime_flags,
        spec=ConfiguredEndpointSpec(
            config_key=f"{_CONFIG_PREFIX}.BASE_URL",
            default_base_url=_DEFAULT_BASE_URL,
            tool_name="news",
            capability="news provider access",
            config_prefix=_CONFIG_PREFIX,
            local_policy_source="MCP news local provider",
            network_blocked_message="News provider network policy blocked access.",
        ),
    )


async def _fetch_news_result(
    utility_tools: MCPUtilityToolsProtocol,
    request: NewsRequest,
) -> JSONDict:
    timeout_sec = coerce_lenient_bounded_float(
        utility_tools.config.get(f"{_CONFIG_PREFIX}.TIMEOUT_SEC"),
        default=20.0,
        minimum=1.0,
        maximum=120.0,
    )
    max_response_bytes = coerce_lenient_positive_int(
        utility_tools.config.get(f"{_CONFIG_PREFIX}.MAX_RESPONSE_BYTES"),
        default=200_000,
        minimum=1,
        maximum=2_000_000,
    )
    if request.top_headlines:
        try:
            provider_payload = await utility_tools.news_article_list_search.search(
                utility_tools,
                request=request,
                timeout_sec=timeout_sec,
            )
        except MCPToolError:
            raise
        except ExternalServiceError as exception:
            raise MCPToolError(-32603, exception.message) from exception
        return build_news_result_payload(
            request,
            provider_payload,
            effective_country="global",
            search_mode=NEWS_SEARCH_MODE_HEADLINE_SUMMARY_GLOBAL,
        )
    cache_key = build_news_cache_key(request)
    network_target = await _resolve_news_network_target(utility_tools)
    try:
        provider_payload = await fetch_news_provider_payload(
            utility_tools,
            url=build_news_url(network_target.base_url, request),
            query_key=cache_key,
            extensions=network_target.extensions,
            timeout_sec=timeout_sec,
            max_response_bytes=max_response_bytes,
        )
    except MCPToolError:
        raise
    except (RateLimitError, ExternalServiceError) as provider_exception:
        try:
            fallback_payload = await utility_tools.news_article_list_search.search(
                utility_tools,
                request=request,
                timeout_sec=timeout_sec,
            )
        except MCPToolError:
            raise
        except ExternalServiceError as fallback_exception:
            should_log, suppressed_count = (
                utility_tools.news_provider_control.fallback_failure_limiter.should_emit()
            )
            if should_log:
                log_handled_exception(
                    get_logger(_LOGGER_NAME),
                    fallback_exception,
                    message="GDELT Article List fallback failed.",
                    operation=OPERATION_GAL_SEARCH,
                    details={"suppressed_count": suppressed_count},
                    level="warning",
                )
            _raise_news_provider_error(provider_exception)
        fallback_result = build_news_result_payload(
            request,
            fallback_payload,
            effective_country="global",
            search_mode=NEWS_SEARCH_MODE_HEADLINE_SUMMARY_GLOBAL,
        )
        if fallback_result["article_count"] == 0:
            _raise_news_provider_error(provider_exception)
        return fallback_result
    return build_news_result_payload(
        request,
        provider_payload,
        effective_country=request.country,
        search_mode=NEWS_SEARCH_MODE_FULLTEXT_COUNTRY,
    )


async def tool_news(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    if not bool(utility_tools.config.get_bool(f"{_CONFIG_PREFIX}.ENABLED")):
        raise MCPToolError(
            -32603,
            "news is disabled by configuration (TOOLS.MCP.NEWS.ENABLED=false).",
        )
    request = build_news_request(arguments)
    cache_key = build_news_cache_key(request)
    return await utility_tools.news_cache.get_or_compute(
        cache_key,
        lambda: _fetch_news_result(utility_tools, request),
    )
