"""SoAI - Plugin worker stream protocol helpers [backend/plugins/worker/stream_protocol.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import base64
import binascii

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from plugins.worker.proxy_payloads import payload_from_message

__all__ = (
    "PLUGIN_STREAM_CHUNK_EVENT",
    "PLUGIN_STREAM_END_EVENT",
    "PLUGIN_STREAM_RESPONSE_KEY",
    "decode_stream_chunk_event",
    "encode_stream_chunk_event",
    "encode_stream_end_event",
    "is_stream_requested_payload",
    "is_stream_response_payload",
)

PLUGIN_STREAM_CHUNK_EVENT = "event.stream_chunk"
PLUGIN_STREAM_END_EVENT = "event.stream_end"
PLUGIN_STREAM_RESPONSE_KEY = "stream"
_PLUGIN_STREAM_BYTES_KEY = "bytes"


def encode_stream_chunk_event(*, request_id: str, chunk: bytes) -> JSONDict:
    if not isinstance(chunk, bytes):
        raise ValidationError("Plugin stream chunks must be bytes.")
    return {
        "type": PLUGIN_STREAM_CHUNK_EVENT,
        "request_id": request_id,
        "payload": {_PLUGIN_STREAM_BYTES_KEY: base64.b64encode(chunk).decode("ascii")},
    }


def encode_stream_end_event(*, request_id: str) -> JSONDict:
    return {"type": PLUGIN_STREAM_END_EVENT, "request_id": request_id, "payload": {}}


def decode_stream_chunk_event(message: JSONDict) -> bytes:
    event_payload = payload_from_message(message)
    encoded = event_payload.get(_PLUGIN_STREAM_BYTES_KEY)
    if not isinstance(encoded, str):
        raise ValidationError("Plugin worker stream chunk is missing bytes.")
    try:
        return base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exception:
        raise ValidationError("Plugin worker stream chunk is invalid.") from exception


def is_stream_response_payload(payload: JSONDict) -> bool:
    return payload.get(PLUGIN_STREAM_RESPONSE_KEY) is True


def is_stream_requested_payload(payload: JSONDict) -> bool:
    return payload.get(PLUGIN_STREAM_RESPONSE_KEY) is True
