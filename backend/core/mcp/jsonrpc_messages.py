"""SoAI - MCP JSON-RPC message classification [backend/core/mcp/jsonrpc_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.mcp.mcp_2025_11_25 import (
    JSON_RPC_VERSION,
    validate_jsonrpc_id,
    validate_jsonrpc_id_for_request,
)
from core.types.json import is_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "JsonRpcMessageClassification",
    "classify_jsonrpc_message",
    "resolve_jsonrpc_params_object",
)


@dataclass(frozen=True, slots=True)
class JsonRpcMessageClassification:
    type: str
    method: str | None
    rpc_id: str | int | None


def _resolve_invalid_message_rpc_id(body: JSONDict) -> str | int | None:
    if "id" not in body:
        return None
    rpc_id_value = body.get("id")
    if rpc_id_value is not None and (
        not isinstance(rpc_id_value, str | int) or isinstance(rpc_id_value, bool)
    ):
        return None
    is_valid_id, rpc_id = validate_jsonrpc_id(rpc_id_value)
    return rpc_id if is_valid_id else None


def classify_jsonrpc_message(
    body: JSONDict,
    *,
    require_jsonrpc_version: bool = True,
) -> JsonRpcMessageClassification:
    if require_jsonrpc_version and body.get("jsonrpc") != JSON_RPC_VERSION:
        return JsonRpcMessageClassification(type="invalid", method=None, rpc_id=None)
    has_method_key = "method" in body
    method_value = body.get("method")
    has_id_key = "id" in body
    rpc_id_value = body.get("id")
    if has_method_key:
        if "result" in body or "error" in body:
            return JsonRpcMessageClassification(
                type="invalid",
                method=None,
                rpc_id=_resolve_invalid_message_rpc_id(body),
            )
        if (
            not isinstance(method_value, str)
            or not method_value
            or method_value != method_value.strip()
        ):
            return JsonRpcMessageClassification(
                type="invalid",
                method=None,
                rpc_id=_resolve_invalid_message_rpc_id(body),
            )
        method = method_value
        if has_id_key:
            if not isinstance(rpc_id_value, str | int) or isinstance(rpc_id_value, bool):
                return JsonRpcMessageClassification(type="invalid", method=method, rpc_id=None)
            is_valid_id, rpc_id = validate_jsonrpc_id_for_request(rpc_id_value)
            if not is_valid_id:
                return JsonRpcMessageClassification(type="invalid", method=method, rpc_id=None)
            return JsonRpcMessageClassification(type="request", method=method, rpc_id=rpc_id)
        return JsonRpcMessageClassification(type="notification", method=method, rpc_id=None)
    if has_id_key:
        if not require_jsonrpc_version and rpc_id_value is None:
            return JsonRpcMessageClassification(type="invalid", method=None, rpc_id=None)
        if rpc_id_value is not None and (
            not isinstance(rpc_id_value, str | int) or isinstance(rpc_id_value, bool)
        ):
            return JsonRpcMessageClassification(type="invalid", method=None, rpc_id=None)
        is_valid_id, rpc_id = validate_jsonrpc_id(rpc_id_value)
        if not is_valid_id:
            return JsonRpcMessageClassification(type="invalid", method=None, rpc_id=None)
        has_result = "result" in body
        has_error = "error" in body
        if has_result == has_error:
            return JsonRpcMessageClassification(type="invalid", method=None, rpc_id=rpc_id)
        return JsonRpcMessageClassification(type="response", method=None, rpc_id=rpc_id)
    return JsonRpcMessageClassification(type="invalid", method=None, rpc_id=None)


def resolve_jsonrpc_params_object(parameters_raw: JSONValue) -> JSONDict:
    if parameters_raw is None:
        return {}
    if is_json_dict(parameters_raw):
        return dict(parameters_raw)
    raise ValidationError(
        f"Invalid params type: expected object, got {type(parameters_raw).__name__}",
    )
