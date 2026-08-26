"""SoAI - MCP storage embedding model availability and automatic selection [backend/mcp/storage/embedding_model_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.mcp.schema import is_auto_embedding_model_sentinel
from core.models.model_info_fields import is_model_info_active_and_enabled
from core.openai.capability_checks import is_openai_capability_enabled
from core.serialization.json_parsing import parse_json_value
from core.validation.strings import coerce_optional_trimmed_str
from mcp.storage.internal_protocols import MCPStorageProtocol

if TYPE_CHECKING:
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ensure_any_embedding_model_available",
    "is_embedding_model_available",
    "resolve_embedding_model_for_embeddings_request",
)


def _normalize_string_entries(value: JSONValue) -> list[str]:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            value = parse_json_value(raw)
        except ValidationError:
            return [raw.lower()]
    if not isinstance(value, list | tuple | set):
        return []
    normalized: list[str] = []
    for item in value:
        entry = str(item or "").strip().lower()
        if entry:
            normalized.append(entry)
    return list(dict.fromkeys(normalized))


def _model_has_embedding_hint(model_id: str, model_info: JSONDict | None) -> bool:
    if model_info:
        capabilities = _normalize_string_entries(model_info.get("capabilities"))
        tags = _normalize_string_entries(model_info.get("tags"))
        model_type_entries = _normalize_string_entries(model_info.get("model_types"))
        model_type_value = str(model_info.get("model_type") or "").strip().lower()
        model_format_value = str(model_info.get("model_format") or "").strip().lower()
        for entry in (
            *capabilities,
            *tags,
            *model_type_entries,
            model_type_value,
            model_format_value,
        ):
            if entry in {"embed", "embedding", "embeddings", "text-embedding"}:
                return True
    return "embed" in model_id.lower()


def _require_embedding_model_services(
    self: MCPStorageProtocol,
) -> tuple[ModelResolutionServiceProtocol, ModelInformationServiceProtocol]:
    try:
        model_resolution_service = self.model_resolution_service
        model_information_service = self.model_information_service
    except AttributeError as exception:
        raise StateError(
            "model_resolution_service and model_information_service are required for embedding availability check",
        ) from exception
    if model_resolution_service is None or model_information_service is None:
        raise StateError(
            "model_resolution_service and model_information_service are required for embedding availability check",
        )
    return model_resolution_service, model_information_service


async def _is_embedding_model_candidate(self: MCPStorageProtocol, model_id: str) -> bool:
    return await _is_embedding_model_candidate_with_hint_requirement(
        self,
        model_id,
        require_hint=True,
    )


async def _is_embedding_model_candidate_with_hint_requirement(
    self: MCPStorageProtocol,
    model_id: str,
    *,
    require_hint: bool,
) -> bool:
    model_resolution_service, model_information_service = _require_embedding_model_services(self)
    normalized_model_id = coerce_optional_trimmed_str(model_id)
    if normalized_model_id is None:
        return False
    universal_id = await model_resolution_service.model_resolve_to_universal_id(normalized_model_id)
    if not universal_id:
        return False
    model_info = await model_information_service.model_get_info(universal_id)
    if not model_info or not isinstance(model_info, dict):
        return False
    if not is_model_info_active_and_enabled(model_info):
        return False
    openai_caps = model_info.get("openai_capabilities")
    if not isinstance(openai_caps, dict) or not is_openai_capability_enabled(
        openai_caps,
        "endpoints",
        "embeddings",
    ):
        return False
    if require_hint:
        return _model_has_embedding_hint(normalized_model_id, model_info)
    return True


async def is_embedding_model_available(self: MCPStorageProtocol, model_id: str) -> bool:
    _require_embedding_model_services(self)
    normalized_model_id = coerce_optional_trimmed_str(model_id)
    if normalized_model_id is None:
        return False
    return await _is_embedding_model_candidate(self, normalized_model_id)


async def resolve_embedding_model_for_embeddings_request(
    self: MCPStorageProtocol,
    embedding_model: str | None,
) -> str:
    requested = coerce_optional_trimmed_str(embedding_model) or "auto"
    if is_auto_embedding_model_sentinel(requested):
        return await ensure_any_embedding_model_available(self)
    if requested.lower() != "auto":
        if not await _is_embedding_model_candidate_with_hint_requirement(
            self,
            requested,
            require_hint=False,
        ):
            raise ValidationError(
                f"Embedding model '{requested}' is not available or does not support embeddings.",
            )
        return requested
    if await is_embedding_model_available(self, "auto"):
        return "auto"
    return await ensure_any_embedding_model_available(self)


async def ensure_any_embedding_model_available(self: MCPStorageProtocol) -> str:
    model_resolution_service, model_information_service = _require_embedding_model_services(self)
    installed_plugins = model_resolution_service.model_get_installed_plugin_names()
    if not isinstance(installed_plugins, list):
        raise StateError("model_get_installed_plugin_names returned an invalid result.")
    normalized_installed_plugins: list[str] = []
    for plugin_name in installed_plugins:
        if not isinstance(plugin_name, str):
            raise StateError("model_get_installed_plugin_names returned an invalid plugin name.")
        normalized_plugin_name = plugin_name.strip()
        if normalized_plugin_name:
            normalized_installed_plugins.append(normalized_plugin_name)
    normalized_installed_plugins = list(dict.fromkeys(normalized_installed_plugins))
    if not normalized_installed_plugins:
        raise ValidationError(
            "No embedding plugin available. Install or enable a plugin that supports the OpenAI embeddings endpoint.",
        )
    plugin_profiles = await asyncio.gather(
        *[
            model_information_service.model_get_plugin_capability_profile(plugin_name)
            for plugin_name in normalized_installed_plugins
        ],
        return_exceptions=False,
    )
    embedding_plugins = [
        plugin_name
        for plugin_name, profile in zip(normalized_installed_plugins, plugin_profiles, strict=True)
        if (
            isinstance(profile, dict)
            and isinstance((openai_caps := profile.get("openai_capabilities")), dict)
            and is_openai_capability_enabled(openai_caps, "endpoints", "embeddings")
        )
    ]
    if not embedding_plugins:
        raise ValidationError(
            "No embedding plugin available. Install or enable a plugin that supports the OpenAI embeddings endpoint.",
        )
    available_models = await model_information_service.model_get_available()
    if not isinstance(available_models, list):
        raise StateError("model_get_available returned an invalid result.")
    embedding_capable_models: list[str] = []
    auto_candidates: list[str] = []
    for model in available_models:
        if not isinstance(model, dict):
            continue
        if not is_model_info_active_and_enabled(model):
            continue
        openai_caps = model.get("openai_capabilities")
        if not isinstance(openai_caps, dict) or not is_openai_capability_enabled(
            openai_caps,
            "endpoints",
            "embeddings",
        ):
            continue
        model_id_value = model.get("id")
        if not isinstance(model_id_value, str):
            continue
        model_id = coerce_optional_trimmed_str(model_id_value)
        if model_id is None:
            continue
        embedding_capable_models.append(model_id)
        if _model_has_embedding_hint(model_id, model):
            auto_candidates.append(model_id)
    if not embedding_capable_models:
        raise ValidationError(
            "No embedding models available. Download an embedding model, or select a specific embedding model in Chat Settings \u2192 TOOLS.RAG.",
        )
    if auto_candidates:
        return auto_candidates[0]
    return embedding_capable_models[0]
