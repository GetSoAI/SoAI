"""SoAI - Hugging Face model search client [backend/plugin_sdk/hf/search.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.errors.exception_logging import log_handled_exception
from core.models.model_type_normalization import normalize_model_type_tokens
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.types.protocols import HttpClientProtocol
from plugin_sdk.hf.client import (
    hf_fetch_catalog,
    hf_fetch_repo_variants,
    hf_prepare_headers,
)
from plugin_sdk.hf.types import (
    RemoteModelSearchError,
    RemoteModelSearchResult,
    RemoteModelSearchVariant,
)
from plugin_sdk.protocols import LoggerProtocol
from plugin_sdk.runtime_network import create_guarded_async_http_client, require_online_mode

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "RemoteModelSearchError",
    "RemoteModelSearchResult",
    "RemoteModelSearchVariant",
    "build_model_search_terms",
    "hf_model_search",
    "resolve_hf_token",
)

_HF_TOKEN_REGEX = r"hf_[A-Za-z0-9]{30,64}"
OPERATION_HF_SEARCH_REPO_VARIANTS = "plugin_sdk.hf.search.repo_variants"


def resolve_hf_token(
    config: ConfigProtocol | None,
    plugin_config: Mapping[str, JSONValue],
    *,
    trace_logger: LoggerProtocol | None = None,
    plugin_key: str = "DOWNLOADER_HF_TOKEN",
) -> str | None:
    token_candidate: str | None = None
    if plugin_config:
        raw_plugin_token = plugin_config.get(plugin_key)
        if isinstance(raw_plugin_token, str):
            stripped = raw_plugin_token.strip()
            if stripped:
                token_candidate = stripped
    if not token_candidate and config is not None:
        raw_global = config.get("MODELS.CREDENTIALS.HUGGINGFACE_TOKEN")
        if isinstance(raw_global, str):
            stripped = raw_global.strip()
            if stripped:
                token_candidate = stripped
    if not token_candidate:
        return None
    if re.fullmatch(_HF_TOKEN_REGEX, token_candidate) is None:
        if trace_logger:
            trace_logger.warning("Ignoring invalid Hugging Face token format.")
        return None
    return token_candidate


def build_model_search_terms(
    query: str,
    *,
    model_types: Sequence[str] | None = None,
    extension_suffixes: Sequence[str] | None = None,
    append_model_types: bool = True,
) -> list[str]:
    normalized_query = (query or "").strip()
    if not normalized_query:
        return []
    terms = [normalized_query]
    suffixes: list[str] = []
    type_collection: Sequence[str] = (
        normalize_model_type_tokens(model_types or ()) if append_model_types else ()
    )
    for collection in (type_collection, extension_suffixes or ()):
        if not collection:
            continue
        for item in collection:
            suffix = item.strip().lower()
            if suffix and suffix not in suffixes:
                suffixes.append(suffix)
    for suffix in suffixes:
        candidate = f"{normalized_query} {suffix}".strip()
        if candidate not in terms:
            terms.append(candidate)
    return terms


def _collapse_whitespace(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.split())


async def hf_model_search(
    query: str,
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    limit: int = 10,
    token: str | None = None,
    libraries: Sequence[str] | None = None,
    model_types: Sequence[str] | None = None,
    file_extensions: Sequence[str] | None = None,
    preference_order: Sequence[str] | None = None,
    branch: str = "main",
    timeout: float = 15.0,
    max_variants_per_repo: int = 12,
    http_client: HttpClientProtocol | None = None,
    trace_logger: LoggerProtocol | None = None,
) -> list[RemoteModelSearchResult]:
    require_online_mode(runtime_flags, source="Hugging Face model search")
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return []
    normalized_model_types = normalize_model_type_tokens(model_types or ())
    extensions = tuple(file_extensions or ())
    preference = tuple(preference_order or ())
    extension_suffixes = tuple(
        dict.fromkeys(
            ext.lstrip(".").lower() for ext in extensions if isinstance(ext, str) and ext
        ),
    )
    search_terms = build_model_search_terms(
        cleaned_query,
        model_types=normalized_model_types,
        extension_suffixes=extension_suffixes,
    )
    if not search_terms:
        return []
    headers = hf_prepare_headers(token)
    client: HttpClientProtocol
    if http_client is None:
        client = create_guarded_async_http_client(
            runtime_flags,
            source="hf_model_search",
            timeout=timeout,
        )
        close_client = True
    else:
        client = http_client
        close_client = False
    try:
        catalog_tasks: list[tuple[str, JSONDict]] = []
        per_term_limit = max(limit, 1)
        for term in search_terms:
            entries = await hf_fetch_catalog(
                client,
                term,
                headers,
                limit=per_term_limit,
                libraries=tuple(libraries or ()),
                timeout=timeout,
                logger=trace_logger,
            )
            for entry in entries:
                repo_id = entry.get("id") or entry.get("modelId")
                if isinstance(repo_id, str) and repo_id:
                    catalog_tasks.append((repo_id, entry))
            if catalog_tasks:
                break
        if not catalog_tasks:
            return []

        async def enrich(repo_id: str, entry: JSONDict) -> RemoteModelSearchResult | None:
            variants: list[RemoteModelSearchVariant] = []
            try:
                variants = await hf_fetch_repo_variants(
                    client,
                    repo_id,
                    headers,
                    branch=branch,
                    file_extensions=extensions,
                    preference_order=preference,
                    timeout=timeout,
                    max_variants=max_variants_per_repo,
                    logger=trace_logger,
                )
            except RemoteModelSearchError as exception:
                if exception.status_code in (401, 403):
                    raise
                if trace_logger:
                    log_handled_exception(
                        trace_logger,
                        exception,
                        message="Skipping Hugging Face repo due to error.",
                        operation=OPERATION_HF_SEARCH_REPO_VARIANTS,
                        details={"repo_id": repo_id},
                        level="debug",
                    )
                return None
            if not variants:
                return None
            tags: list[str] = []
            entry_tags = entry.get("tags")
            if isinstance(entry_tags, list):
                tags.extend([str(tag) for tag in entry_tags if tag])
            pipeline_tag = entry.get("pipeline_tag")
            if isinstance(pipeline_tag, str):
                tags.append(pipeline_tag)
            card_data = entry.get("cardData")
            summary = entry.get("description")
            if isinstance(card_data, dict) and (not summary):
                summary = card_data.get("summary")
            metadata_payload: JSONDict = {
                "author": entry.get("author"),
                "sha": entry.get("sha"),
                "pipeline_tag": entry.get("pipeline_tag"),
            }
            if normalized_model_types:
                metadata_payload["model_types"] = list(normalized_model_types)
            name_value = entry.get("modelId") or entry.get("id") or repo_id
            name = str(name_value).strip() or repo_id
            summary_text = summary if isinstance(summary, str) else None
            score_value = entry.get("likes") or entry.get("downloads")
            score: int | None = None
            if isinstance(score_value, int | float | str):
                try:
                    score = int(float(str(score_value).strip()))
                except (TypeError, ValueError):
                    score = None
            return RemoteModelSearchResult(
                id=repo_id,
                name=name,
                source="huggingface",
                summary=_collapse_whitespace(summary_text) or "",
                score=score,
                tags=tags,
                metadata=metadata_payload,
                variants=variants,
            )

        enrich_tasks = [enrich(repo_id, entry) for repo_id, entry in catalog_tasks]
        enriched = await asyncio.gather(*enrich_tasks, return_exceptions=True)
        results: list[RemoteModelSearchResult] = []
        for enriched_item in enriched:
            if isinstance(enriched_item, RemoteModelSearchResult):
                results.append(enriched_item)
            elif isinstance(enriched_item, asyncio.CancelledError):
                raise enriched_item
            if isinstance(enriched_item, BaseException):
                if isinstance(enriched_item, RemoteModelSearchError):
                    raise enriched_item
                status_code = None
                error_type_name = type(enriched_item).__name__
                raise RemoteModelSearchError(
                    f"Hugging Face model search failed: {error_type_name}: {enriched_item}",
                    status_code=status_code,
                ) from enriched_item
        return results[:limit]
    finally:
        if close_client:
            await client.aclose()
