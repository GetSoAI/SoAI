"""SoAI - Chroma IPC worker operations and dispatch [backend/mcp/storage/chroma_ipc_worker_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from chromadb.api import ClientAPI
from chromadb.errors import NotFoundError

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.validation.strings import coerce_optional_trimmed_str
from mcp.storage.chroma_json_results import (
    normalize_chroma_get_result,
    normalize_chroma_query_result,
)
from mcp.storage.chroma_payload_coercion import (
    coerce_include,
    coerce_metadata_list,
    coerce_payload_int,
    coerce_py_embeddings_list,
    coerce_query_embeddings,
    coerce_str_list,
    coerce_where,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("execute_chroma_op",)

LOGGER_NAME = "SoAI.mcp.storage.chroma_ipc_worker_operations"
OPERATION = "mcp.storage.chroma_worker.ensure_collection.modify"


def _cancelled(cancel_path: str | None) -> bool:
    if not cancel_path:
        return False
    return os.path.exists(cancel_path)


def _ensure_collection(client: ClientAPI, payload: JSONDict) -> None:
    collection_name = str(payload.get("collection_name") or "").strip()
    embedding_model_value = payload.get("embedding_model")
    effective_model_value = payload.get("effective_model")
    embedding_model = coerce_optional_trimmed_str(
        embedding_model_value if isinstance(embedding_model_value, str) else None,
    )
    effective_model = coerce_optional_trimmed_str(
        effective_model_value if isinstance(effective_model_value, str) else None,
    )
    if not collection_name:
        raise ValidationError("collection_name is required.")
    if embedding_model is None:
        raise ValidationError("embedding_model is required.")
    if effective_model is None:
        raise ValidationError("effective_model is required.")
    try:
        get_or_create_collection = client.get_or_create_collection
    except AttributeError as exception:
        raise ValidationError("Invalid Chroma client.") from exception
    if not callable(get_or_create_collection):
        raise ValidationError("Invalid Chroma client.")
    collection = get_or_create_collection(
        name=collection_name,
        metadata={"embedding_model": embedding_model, "effective_model": effective_model},
    )
    try:
        modify_method = collection.modify
    except AttributeError:
        modify_method = None
    if callable(modify_method):
        try:
            modify_method(
                metadata={"embedding_model": embedding_model, "effective_model": effective_model},
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            logger = get_logger(LOGGER_NAME)
            error = coerce_to_soai_error(
                exception,
                operation="mcp.storage.chroma_worker.ensure_collection.modify",
                details={"collection_name": collection_name},
            )
            log_handled_exception(
                logger,
                error,
                message="Failed to update Chroma collection metadata (non-critical).",
                operation=OPERATION,
                details={"collection_name": collection_name},
                level="debug",
            )


def _add_upsert(client: ClientAPI, payload: JSONDict, cancel_path: str | None) -> None:
    collection_name = str(payload.get("collection_name") or "").strip()
    ids = coerce_str_list(payload.get("ids"), "ids")
    documents = coerce_str_list(payload.get("documents"), "documents")
    embeddings = coerce_py_embeddings_list(payload.get("embeddings"), "embeddings")
    metadatas = coerce_metadata_list(payload.get("metadatas"), "metadatas")
    batch_size = coerce_payload_int(payload, "batch_size", default=256)
    if not collection_name:
        raise ValidationError("collection_name is required.")
    if len(ids) != len(documents) or len(ids) != len(embeddings) or len(ids) != len(metadatas):
        raise ValidationError("Chroma add payload length mismatch.")
    if batch_size < 1:
        batch_size = 256
    collection = client.get_or_create_collection(name=collection_name)
    try:
        upsert_fn = collection.upsert
    except AttributeError:
        upsert_fn = None
    upsert_callable = upsert_fn if callable(upsert_fn) else None
    if upsert_callable is None:
        raise ValidationError("Chroma collection does not support upsert; refusing write.")
    for start in range(0, len(ids), batch_size):
        if _cancelled(cancel_path):
            raise asyncio.CancelledError("Cancelled")
        end = start + batch_size
        upsert_callable(
            ids=list(ids[start:end]),
            embeddings=list(embeddings[start:end]),
            documents=list(documents[start:end]),
            metadatas=list(metadatas[start:end]),
        )
        if _cancelled(cancel_path):
            raise asyncio.CancelledError("Cancelled")


def _query(client: ClientAPI, payload: JSONDict) -> JSONDict | None:
    collection_name = str(payload.get("collection_name") or "").strip()
    query_embeddings = coerce_query_embeddings(payload.get("query_embeddings"), "query_embeddings")
    n_results = coerce_payload_int(payload, "n_results", default=1)
    where_raw = payload.get("where")
    include = coerce_include(payload.get("include"), "include")
    if not collection_name:
        raise ValidationError("collection_name is required.")
    where_value = coerce_where(where_raw, "where") if isinstance(where_raw, dict) else None
    try:
        collection = client.get_collection(collection_name)
    except NotFoundError:
        return None
    raw = collection.query(
        query_embeddings=query_embeddings,
        n_results=max(1, n_results),
        where=where_value,
        include=include,
    )
    normalized = normalize_chroma_query_result(raw)
    if isinstance(normalized, dict):
        return normalized
    raise ValidationError("Chroma query returned a non-JSON-object payload.")


def _get(client: ClientAPI, payload: JSONDict) -> JSONDict | None:
    collection_name = str(payload.get("collection_name") or "").strip()
    ids_raw = payload.get("ids")
    where_raw = payload.get("where")
    include = coerce_include(payload.get("include"), "include")
    if not collection_name:
        raise ValidationError("collection_name is required.")
    ids_value = coerce_str_list(ids_raw, "ids") if isinstance(ids_raw, list) else None
    where_value = coerce_where(where_raw, "where") if isinstance(where_raw, dict) else None
    try:
        collection = client.get_collection(collection_name)
    except NotFoundError:
        return None
    raw = collection.get(ids=ids_value, where=where_value, include=include)
    normalized = normalize_chroma_get_result(raw)
    if isinstance(normalized, dict):
        return normalized
    raise ValidationError("Chroma get returned a non-JSON-object payload.")


def _delete(client: ClientAPI, payload: JSONDict) -> None:
    collection_name = str(payload.get("collection_name") or "").strip()
    ids_raw = payload.get("ids")
    where_raw = payload.get("where")
    if not collection_name:
        raise ValidationError("collection_name is required.")
    try:
        collection = client.get_collection(collection_name)
    except NotFoundError:
        return
    ids_value = coerce_str_list(ids_raw, "ids") if isinstance(ids_raw, list) else None
    where_value = coerce_where(where_raw, "where") if isinstance(where_raw, dict) else None
    if ids_value is None and where_value is None:
        return
    collection.delete(ids=ids_value, where=where_value)


def _delete_collection(client: ClientAPI, payload: JSONDict) -> None:
    collection_name = str(payload.get("collection_name") or "").strip()
    if not collection_name:
        raise ValidationError("collection_name is required.")
    try:
        client.delete_collection(collection_name)
        return
    except NotFoundError:
        return


def _list_collections(client: ClientAPI) -> list[str]:
    out: list[str] = []
    for item in client.list_collections():
        try:
            name = item.name
        except AttributeError:
            name = None
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
    return out


def _count(client: ClientAPI, payload: JSONDict) -> int:
    collection_name = str(payload.get("collection_name") or "").strip()
    if not collection_name:
        raise ValidationError("collection_name is required.")
    try:
        collection = client.get_collection(collection_name)
    except NotFoundError:
        return 0
    return int(collection.count() or 0)


def execute_chroma_op(
    client: ClientAPI,
    *,
    op: str,
    payload: JSONDict,
    cancel_path: str | None,
) -> JSONValue:
    if op == "chroma.ensure_collection":
        _ensure_collection(client, payload)
        return True
    if op == "chroma.add_upsert":
        _add_upsert(client, payload, cancel_path)
        return True
    if op == "chroma.query":
        return _query(client, payload)
    if op == "chroma.get":
        return _get(client, payload)
    if op == "chroma.delete":
        _delete(client, payload)
        return True
    if op == "chroma.delete_collection":
        _delete_collection(client, payload)
        return True
    if op == "chroma.list_collections":
        return _list_collections(client)
    if op == "chroma.count":
        return _count(client, payload)
    raise ValidationError(f"Unknown op: {op}")
