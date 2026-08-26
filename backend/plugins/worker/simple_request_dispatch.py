"""SoAI - Plugin worker capability request dispatch [backend/plugins/worker/simple_request_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import inspect
from collections.abc import Awaitable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.models.remote_model_search_types import RemoteModelSearchResult
from core.plugins.base_plugin import BasePlugin
from core.serialization.json import normalize_for_json
from core.types.json import JSONDict, JSONValue
from plugins.worker.payload_fields import (
    read_dict_field,
    read_int_field,
    read_worker_request_str_field,
)
from plugins.worker.runtime_loader import read_model_map
from plugins.worker.serialization import decode_model_context, decode_request_context

__all__ = ("dispatch_simple_plugin_call",)

WORKER_FIELD_LABEL = "Worker request field"

if TYPE_CHECKING:
    type SimplePluginCallResult = (
        JSONValue
        | dict[str, JSONDict]
        | list[JSONDict]
        | tuple[bool, str]
        | list[RemoteModelSearchResult]
    )


async def dispatch_simple_plugin_call(
    plugin: BasePlugin,
    *,
    method: str,
    payload: JSONDict,
) -> JSONDict:
    result: SimplePluginCallResult
    if method == "call.discover_models":
        result = await plugin.discover_models(read_model_map(payload, "existing_models"))
    elif method == "call.get_status":
        result = await plugin.get_status()
    elif method == "call.get_available_variants":
        result = await plugin.get_available_variants(
            read_worker_request_str_field(payload, "model_id"),
        )
    elif method == "call.get_backend_process_pids":
        result = await plugin.get_backend_process_pids()
    elif method == "call.health_ping":
        result = await plugin.health_ping()
    elif method == "call.start":
        result = await _await_bool(plugin.start())
    elif method == "call.start_with_model":
        result = await plugin.start_with_model(
            decode_model_context(
                read_dict_field(payload, "model_context", label=WORKER_FIELD_LABEL),
            ),
            decode_request_context(read_dict_field(payload, "context", label=WORKER_FIELD_LABEL)),
        )
    elif method == "call.stop":
        result = await plugin.stop()
    elif method == "call.cancel_task":
        result = await plugin.cancel_task(
            read_worker_request_str_field(payload, "task_id"),
            decode_request_context(read_dict_field(payload, "context", label=WORKER_FIELD_LABEL)),
        )
    elif method == "call.cleanup_partial_installation":
        await plugin.cleanup_partial_installation()
        result = None
    elif method == "call.load_model_in_service":
        result = await plugin.load_model_in_service(
            decode_model_context(
                read_dict_field(payload, "model_context", label=WORKER_FIELD_LABEL),
            ),
            decode_request_context(read_dict_field(payload, "context", label=WORKER_FIELD_LABEL)),
        )
    elif method == "call.unload_model_in_service":
        result = await plugin.unload_model_in_service(
            read_worker_request_str_field(payload, "universal_id"),
        )
    elif method == "call.handle_embedding_request":
        result = await plugin.handle_embedding_request(
            read_dict_field(payload, "request_json", label=WORKER_FIELD_LABEL),
            decode_request_context(read_dict_field(payload, "context", label=WORKER_FIELD_LABEL)),
            decode_model_context(
                read_dict_field(payload, "model_context", label=WORKER_FIELD_LABEL),
            ),
        )
    elif method == "call.count_prompt_tokens":
        result = await plugin.count_prompt_tokens(
            read_dict_field(payload, "request_json", label=WORKER_FIELD_LABEL),
            decode_request_context(read_dict_field(payload, "context", label=WORKER_FIELD_LABEL)),
            decode_model_context(
                read_dict_field(payload, "model_context", label=WORKER_FIELD_LABEL),
            ),
        )
    elif method == "call.check_for_backend_update":
        result = await plugin.check_for_backend_update()
    elif method == "call.search_remote_models":
        result = await plugin.search_remote_models(
            read_worker_request_str_field(payload, "query"),
            limit=read_int_field(payload, "limit", label=WORKER_FIELD_LABEL, default=10),
        )
    else:
        raise ValidationError(f"Unsupported plugin worker method '{method}'.")
    return {"value": normalize_for_json(result)}


async def _await_bool(value: bool | Awaitable[bool]) -> bool:
    if inspect.isawaitable(value):
        resolved = await value
    else:
        resolved = value
    if not isinstance(resolved, bool):
        raise ValidationError("Plugin start result must be a boolean.")
    return resolved
