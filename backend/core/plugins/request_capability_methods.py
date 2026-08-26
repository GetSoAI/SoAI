"""SoAI - Core base plugin capability fallback methods [backend/core/plugins/request_capability_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.models.remote_model_search_types import RemoteModelSearchResult
from core.plugins.prompt_token_counting import build_unsupported_prompt_token_count_result
from core.plugins.protocols_instance import ModelContextProtocol
from core.plugins.protocols_runtime import BasePluginCapabilitySurfaceProtocol
from core.runtime.request_context import RequestContext
from core.types.json import JSONDict

__all__ = (
    "get_available_variants_method",
    "handle_embedding_request_method",
    "count_prompt_tokens_method",
    "search_remote_models_method",
)


async def handle_embedding_request_method(
    self: BasePluginCapabilitySurfaceProtocol,
    request_json: JSONDict,
    context: RequestContext,
    model_context: ModelContextProtocol,
) -> JSONDict:
    request_model = None
    if isinstance(request_json, dict):
        request_model = request_json.get("model")
    trace_id = context.trace_id
    model_identifier = model_context.universal_id
    detail_suffix = ""
    if request_model or trace_id or model_identifier:
        detail_suffix = (
            f" (model={model_identifier}, request_model={request_model}, trace_id={trace_id})"
        )
    if self.SUPPORTS_EMBEDDINGS:
        raise StateError(
            f"Plugin '{self.plugin_name}' declares embedding support but does not provide an implementation.{detail_suffix}",
        )
    raise StateError(f"Plugin '{self.plugin_name}' does not support embeddings.{detail_suffix}")


async def get_available_variants_method(
    self: BasePluginCapabilitySurfaceProtocol,
    model_id: str,
) -> list[JSONDict]:
    if self.SUPPORTS_MODEL_VARIANT_DISCOVERY:
        raise StateError(
            f"Plugin '{self.plugin_name}' declares variant discovery support but does not provide an implementation. (model_id={model_id!r})",
        )
    return []


async def count_prompt_tokens_method(
    self: BasePluginCapabilitySurfaceProtocol,
    request_json: JSONDict,
    context: RequestContext,
    model_context: ModelContextProtocol,
) -> JSONDict:
    _ = (request_json, context, model_context)
    if self.SUPPORTS_PROMPT_TOKEN_COUNTING:
        raise StateError(
            f"Plugin '{self.plugin_name}' declares prompt token counting support but does not provide an implementation.",
        )
    return build_unsupported_prompt_token_count_result(
        reason=f"Plugin '{self.plugin_name}' does not expose an exact prompt tokenizer.",
    )


async def search_remote_models_method(
    self: BasePluginCapabilitySurfaceProtocol,
    query: str,
    limit: int = 10,
) -> list[RemoteModelSearchResult]:
    if self.SUPPORTS_MODEL_SEARCH:
        raise StateError(
            f"Plugin '{self.plugin_name}' declares remote model search support but does not provide an implementation. (query={query!r}, limit={limit})",
        )
    return []
