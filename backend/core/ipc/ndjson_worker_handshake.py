"""SoAI - NDJSON IPC worker connection handshake helpers [backend/core/ipc/ndjson_worker_handshake.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.errors.exceptions import ValidationError
from core.ipc.settings import build_ndjson_codec_from_env
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.types.json import JSONDict

__all__ = ("connect_ndjson_ipc_worker_session",)


async def connect_ndjson_ipc_worker_session(
    *,
    worker_label: str,
    host_env_key: str = "SOAI_IPC_HOST",
    port_env_key: str = "SOAI_IPC_PORT",
    token_env_key: str = "SOAI_IPC_TOKEN",
    worker_id_env_key: str = "SOAI_IPC_WORKER_ID",
    worker_secret_env_key: str = "SOAI_IPC_WORKER_SECRET",
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter, int]:
    host = str(os.environ.get(host_env_key, "127.0.0.1")).strip() or "127.0.0.1"
    port_raw = str(os.environ.get(port_env_key, "")).strip()
    token = str(os.environ.get(token_env_key, "")).strip()
    worker_id_raw = str(os.environ.get(worker_id_env_key, "")).strip()
    worker_secret = str(os.environ.get(worker_secret_env_key, "")).strip()
    if not port_raw:
        raise ValidationError(f"{port_env_key} is required for {worker_label}.")
    if not token:
        raise ValidationError(f"{token_env_key} is required for {worker_label}.")
    if not worker_id_raw:
        raise ValidationError(f"{worker_id_env_key} is required for {worker_label}.")
    port = int(port_raw)
    worker_id = int(worker_id_raw)
    codec = build_ndjson_codec_from_env()
    reader, writer = await asyncio.open_connection(
        host=host,
        port=port,
        limit=codec.stream_limit_bytes,
    )
    hello: JSONDict = {"type": "hello", "token": token, "worker_id": worker_id}
    if worker_secret:
        hello["worker_secret"] = worker_secret
    await codec.write_message(
        writer,
        hello,
        timeout_sec=LOCAL_IO_TIMEOUT_SEC,
    )
    ack = await codec.read_message(reader, timeout_sec=LOCAL_IO_TIMEOUT_SEC)
    if ack.get("type") != "hello_ack":
        raise ValidationError("IPC hello_ack missing from server.")
    return reader, writer, worker_id
