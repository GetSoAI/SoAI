"""SoAI - Durable mutation request identifiers [backend/core/mutations/identifiers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
import secrets
import time

from core.errors.exceptions import ValidationError
from core.tasks.cancellation_ids import require_cancellation_id
from core.validation.strict_numbers import require_positive_int_strict

_LOWERCASE_UUID_V7_PATTERN = (
    r"[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)
_OPERATION_PREFIX_PATTERN = r"[a-z][a-z0-9]{1,15}\Z"


def require_mutation_request_id(value: str) -> str:
    if isinstance(value, str) and re.fullmatch(_LOWERCASE_UUID_V7_PATTERN, value):
        return value
    raise ValidationError("Mutation request ID must be a lowercase UUIDv7.")


def extract_mutation_request_timestamp_ms(value: str) -> int:
    request_id = require_mutation_request_id(value)
    return int(request_id[0:8] + request_id[9:13], 16)


def create_mutation_request_id() -> str:
    timestamp_ms = int(time.time() * 1000)
    if timestamp_ms < 0 or timestamp_ms >= 1 << 48:
        raise ValidationError("Current time cannot be represented by a UUIDv7.")
    random_bytes = bytearray(secrets.token_bytes(10))
    raw = bytearray(timestamp_ms.to_bytes(6, "big") + random_bytes)
    raw[6] = (raw[6] & 0x0F) | 0x70
    raw[8] = (raw[8] & 0x3F) | 0x80
    hexadecimal = raw.hex()
    first_segments = f"{hexadecimal[:8]}-{hexadecimal[8:12]}-{hexadecimal[12:16]}"
    final_segments = f"{hexadecimal[16:20]}-{hexadecimal[20:]}"
    return require_mutation_request_id(f"{first_segments}-{final_segments}")


def create_timestamped_operation_id(prefix: str) -> str:
    normalized_prefix = require_operation_id_prefix(prefix)
    return f"{normalized_prefix}_{create_mutation_request_id()}"


def require_operation_id_prefix(prefix: str) -> str:
    if isinstance(prefix, str) and re.fullmatch(_OPERATION_PREFIX_PATTERN, prefix):
        return prefix
    raise ValidationError("Operation ID prefix is invalid.")


def require_timestamped_operation_id(value: str, prefix: str) -> str:
    normalized_prefix = require_operation_id_prefix(prefix)
    expected_prefix = f"{normalized_prefix}_"
    if not isinstance(value, str) or not value.startswith(expected_prefix):
        raise ValidationError("Operation ID is invalid.")
    require_mutation_request_id(value[len(expected_prefix) :])
    return value


def extract_timestamped_operation_id_ms(value: str, prefix: str) -> int:
    normalized = require_timestamped_operation_id(value, prefix)
    return extract_mutation_request_timestamp_ms(normalized[len(prefix) + 1 :])


def build_mutation_claim_cancellation_id(
    base_cancellation_id: str,
    request_id: str,
    fencing_token: int,
) -> str:
    base = require_cancellation_id(base_cancellation_id)
    normalized_request_id = require_mutation_request_id(request_id)
    normalized_fencing_token = require_positive_int_strict(
        fencing_token,
        error_message="Mutation claim cancellation requires a positive fencing token.",
    )
    return f"{base}::mutation::claim::{normalized_request_id}::{normalized_fencing_token}"


__all__ = (
    "build_mutation_claim_cancellation_id",
    "create_mutation_request_id",
    "create_timestamped_operation_id",
    "extract_mutation_request_timestamp_ms",
    "extract_timestamped_operation_id_ms",
    "require_mutation_request_id",
    "require_operation_id_prefix",
    "require_timestamped_operation_id",
)
