"""SoAI - Discord gateway payload coercion [backend/core/messaging/discord_gateway_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONDict
from core.validation.record_fields import require_json_object, require_number

__all__ = (
    "parse_discord_gateway_payload",
    "resolve_discord_heartbeat_interval_sec",
)


def parse_discord_gateway_payload(raw_payload: bytes | bytearray | str) -> JSONDict:
    if isinstance(raw_payload, bytearray):
        payload_raw: str | bytes = bytes(raw_payload)
    elif isinstance(raw_payload, bytes | str):
        payload_raw = raw_payload
    else:
        payload_raw = str(raw_payload)
    parsed = parse_json_value(payload_raw, field="Discord gateway payload")
    return require_json_object(
        parsed,
        label="Discord gateway payload",
        build_error=ValueError,
        invalid_message="Discord gateway payload is not a JSON object.",
    )


def resolve_discord_heartbeat_interval_sec(hello_data: JSONDict) -> float:
    heartbeat_interval_value = hello_data.get("heartbeat_interval")
    heartbeat_interval_number = require_number(
        heartbeat_interval_value,
        label="Discord gateway heartbeat interval",
        build_error=ValueError,
        invalid_message="Discord gateway heartbeat interval is invalid.",
        finite_message="Discord gateway heartbeat interval is invalid.",
    )
    return max(1.0, float(heartbeat_interval_number) / 1000.0)
