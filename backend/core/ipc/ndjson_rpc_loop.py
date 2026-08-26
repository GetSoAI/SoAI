"""SoAI - NDJSON IPC request loop for worker processes [backend/core/ipc/ndjson_rpc_loop.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.public_projection import project_public_error
from core.ipc.ndjson import IpcStreamClosedError
from core.ipc.settings import build_ndjson_codec_from_env
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.types.json import JSONDict, JSONValue

__all__ = (
    "NdjsonRpcRequest",
    "NdjsonRpcResponse",
    "build_ndjson_rpc_error_response",
    "build_ndjson_rpc_ok_response",
    "run_ndjson_rpc_loop",
)


@dataclass(frozen=True, slots=True)
class NdjsonRpcRequest:
    request_id: str
    method: str
    payload: JSONValue


@dataclass(frozen=True, slots=True)
class NdjsonRpcResponse:
    request_id: str
    ok: bool
    payload: JSONDict | None = None


def build_ndjson_rpc_error_response(
    request_id: str,
    *,
    error: str,
    message: str,
) -> JSONDict:
    return {
        "type": "response",
        "request_id": request_id,
        "ok": False,
        "payload": {"error": str(error), "message": str(message)},
    }


def build_ndjson_rpc_ok_response(request_id: str, payload: JSONDict | None = None) -> JSONDict:
    response_payload = dict(payload or {})
    return {
        "type": "response",
        "request_id": request_id,
        "ok": True,
        "payload": response_payload,
    }


async def run_ndjson_rpc_loop(
    *,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    idle_timeout_sec: float,
    handle_request: Callable[[NdjsonRpcRequest], Awaitable[NdjsonRpcResponse]],
    response_timeout_sec: float = LOCAL_IO_TIMEOUT_SEC,
) -> None:
    codec = build_ndjson_codec_from_env()
    while True:
        try:
            message = await codec.read_message(reader, timeout_sec=float(idle_timeout_sec))
        except TimeoutError:
            continue
        except IpcStreamClosedError:
            return
        if message.get("type") != "request":
            continue
        request_id = str(message.get("request_id") or "").strip()
        method = str(message.get("method") or "").strip()
        payload: JSONValue = message.get("payload")
        if not request_id:
            response = build_ndjson_rpc_error_response(
                "missing",
                error="invalid_request",
                message="Missing request_id.",
            )
            await codec.write_message(writer, response, timeout_sec=float(response_timeout_sec))
            continue
        if not method:
            response = build_ndjson_rpc_error_response(
                request_id,
                error="invalid_request",
                message="Missing method.",
            )
            await codec.write_message(writer, response, timeout_sec=float(response_timeout_sec))
            continue
        try:
            response_obj = await handle_request(
                NdjsonRpcRequest(request_id=request_id, method=method, payload=payload),
            )
        except ValidationError as exception:
            public_error = project_public_error(exception)
            response = build_ndjson_rpc_error_response(
                request_id,
                error="validation_error",
                message=public_error.message,
            )
            await codec.write_message(writer, response, timeout_sec=float(response_timeout_sec))
            continue
        response_payload = response_obj.payload if response_obj.payload is not None else {}
        if response_obj.ok:
            response = build_ndjson_rpc_ok_response(response_obj.request_id, response_payload)
        else:
            error_value = (
                response_payload.get("error") if isinstance(response_payload, dict) else None
            )
            error_text = str(error_value) if error_value is not None else "request_failed"
            response = build_ndjson_rpc_error_response(
                response_obj.request_id,
                error=error_text,
                message=str(response_payload.get("message") or ""),
            )
        await codec.write_message(writer, response, timeout_sec=float(response_timeout_sec))
