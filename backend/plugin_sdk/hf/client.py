"""SoAI - Hugging Face API client for model search operations [backend/plugin_sdk/hf/client.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx2

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.network.http_json import read_http_json_value
from core.network.outbound_http_profiles import build_model_registry_headers
from core.types.json_value import coerce_json_dict
from core.types.protocols import HttpClientProtocol
from plugin_sdk.hf.types import RemoteModelSearchError, RemoteModelSearchVariant
from plugin_sdk.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ()

_HF_MODELS_ENDPOINT = "https://huggingface.co/api/models"
_HF_TREE_ENDPOINT_TEMPLATE = "https://huggingface.co/api/models/{repo}/tree/{branch}"
_HF_RESOLVE_TEMPLATE = "https://huggingface.co/{repo}/resolve/{branch}/{path}"
OPERATION_HF_CLIENT_REQUEST = "plugin_sdk.hf.client.request"


def hf_prepare_headers(token: str | None) -> dict[str, str]:
    return build_model_registry_headers(bearer_token=token)


def _hf_variant_sort_key(
    variant: RemoteModelSearchVariant,
    preference_order: Sequence[str],
) -> tuple[int, int]:
    name = variant.name.lower()
    for index, token in enumerate(preference_order):
        if token and token.lower() in name:
            return (index, len(name))
    return (len(preference_order), len(name))


def _hf_should_skip_split(path: str) -> bool:
    lowered = path.lower()
    if "-of-" not in lowered:
        return False
    return "-00001-of-" not in lowered


async def _hf_request_json(
    client: HttpClientProtocol,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, str | int] | None = None,
    timeout: float,
    logger: LoggerProtocol | None = None,
) -> JSONValue:
    try:
        response = await client.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )
        response.raise_for_status()
        return read_http_json_value(response, field="Hugging Face response")
    except httpx2.HTTPStatusError as exception:
        status_code = exception.response.status_code
        message = f"Hugging Face request failed ({status_code})"
        if logger:
            logger.debug("%s url=%s params=%s", message, url, params)
        raise RemoteModelSearchError(
            message,
            status_code=status_code,
            retryable=status_code >= 500,
        ) from exception
    except httpx2.HTTPError as exception:
        if logger:
            details: JSONDict = {"url": url}
            if params is not None:
                details["params"] = dict(params)
            log_exception(
                logger,
                exception,
                message="Hugging Face request error (non-critical).",
                operation=OPERATION_HF_CLIENT_REQUEST,
                details=details,
                level="debug",
            )
        raise RemoteModelSearchError(
            "Hugging Face request failed",
            retryable=True,
        ) from exception
    except ValidationError as exception:
        if logger:
            log_exception(
                logger,
                exception,
                message="Hugging Face response JSON was invalid (non-critical).",
                operation=OPERATION_HF_CLIENT_REQUEST,
                details={"url": url},
                level="debug",
            )
        raise RemoteModelSearchError(
            "Hugging Face response was not valid JSON",
            retryable=True,
        ) from exception


async def hf_fetch_catalog(
    client: HttpClientProtocol,
    query: str,
    headers: dict[str, str],
    limit: int,
    libraries: Sequence[str],
    timeout: float,
    logger: LoggerProtocol | None,
) -> list[JSONDict]:
    seen_ids: set[str] = set()
    entries: list[JSONDict] = []
    if not query:
        return entries
    library_candidates = libraries or (None,)
    for library in library_candidates:
        params: dict[str, str | int] = {"search": query, "limit": limit}
        if library:
            params["library"] = library
        try:
            payload = await _hf_request_json(
                client,
                _HF_MODELS_ENDPOINT,
                headers=headers,
                params=params,
                timeout=timeout,
                logger=logger,
            )
        except RemoteModelSearchError as exception:
            if exception.status_code in (401, 403):
                raise
            continue
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            repo_id_value = item.get("id") or item.get("modelId")
            repo_id = repo_id_value if isinstance(repo_id_value, str) else None
            if not repo_id or repo_id in seen_ids:
                continue
            seen_ids.add(repo_id)
            normalized = coerce_json_dict(item)
            if normalized is None:
                continue
            entries.append(normalized)
            if len(entries) >= limit:
                break
        if entries:
            break
    return entries


async def hf_fetch_repo_variants(
    client: HttpClientProtocol,
    repo_id: str,
    headers: dict[str, str],
    *,
    branch: str,
    file_extensions: Sequence[str],
    preference_order: Sequence[str],
    timeout: float,
    max_variants: int,
    logger: LoggerProtocol | None,
) -> list[RemoteModelSearchVariant]:
    repo_segment = quote(repo_id, safe="/")
    tree_url = f"https://huggingface.co/api/models/{repo_segment}/tree/{branch}"
    params: dict[str, str | int] = {"recursive": "true"}
    payload = await _hf_request_json(
        client,
        tree_url,
        headers=headers,
        params=params,
        timeout=timeout,
        logger=logger,
    )
    if not isinstance(payload, list):
        return []
    variants: list[RemoteModelSearchVariant] = []
    for node in payload:
        if not isinstance(node, dict):
            continue
        if node.get("type") != "file":
            continue
        path_value = node.get("path") or node.get("rfilename")
        path = path_value if isinstance(path_value, str) else None
        if not path:
            continue
        lowered = path.lower()
        if not any(lowered.endswith(ext.lower()) for ext in file_extensions):
            continue
        if _hf_should_skip_split(lowered):
            continue
        size_value = None
        size_raw = node.get("size")
        if isinstance(size_raw, int | float | str):
            try:
                size_value = int(float(str(size_raw).strip()))
            except (ValueError, TypeError):
                size_value = None
        download_path = quote(path)
        download_uri = f"https://huggingface.co/{repo_segment}/resolve/{branch}/{download_path}"
        checksum_value = node.get("oid") or node.get("sha")
        checksum = checksum_value if isinstance(checksum_value, str) else ""
        variant = RemoteModelSearchVariant(
            id=f"{repo_id}:{path}",
            name=os.path.basename(path),
            uri=download_uri,
            size_bytes=size_value,
            checksum=checksum,
            extra={"path": path},
        )
        variants.append(variant)
    ordered = (
        sorted(variants, key=lambda variant: _hf_variant_sort_key(variant, preference_order))
        if preference_order
        else variants
    )
    return ordered[:max_variants]
