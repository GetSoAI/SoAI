"""SoAI - Immutable HTTP request body policy [backend/features/api/request_body_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from dataclasses import dataclass

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.validation.strict_numbers import require_positive_int_strict

__all__ = (
    "RequestBodyPolicy",
    "build_request_body_policy",
)


@dataclass(frozen=True, slots=True)
class RequestBodyPolicy:
    openai_max_bytes: int
    native_max_bytes: int
    read_deadline_seconds: float


def build_request_body_policy(config: ConfigProtocol) -> RequestBodyPolicy:
    openai_max_bytes = _require_positive_config_int(
        config,
        "SERVER.HTTP.REQUEST_BODY.OPENAI_MAX_BYTES",
    )
    native_max_bytes = _require_positive_config_int(
        config,
        "SERVER.HTTP.REQUEST_BODY.NATIVE_MAX_BYTES",
    )
    raw_deadline = config.get("SERVER.HTTP.REQUEST_BODY.READ_DEADLINE_SEC")
    if isinstance(raw_deadline, bool) or not isinstance(raw_deadline, int | float):
        raise ValidationError(
            "SERVER.HTTP.REQUEST_BODY.READ_DEADLINE_SEC must be a positive finite number."
        )
    read_deadline_seconds = float(raw_deadline)
    if not math.isfinite(read_deadline_seconds) or read_deadline_seconds <= 0.0:
        raise ValidationError(
            "SERVER.HTTP.REQUEST_BODY.READ_DEADLINE_SEC must be a positive finite number."
        )
    return RequestBodyPolicy(
        openai_max_bytes=openai_max_bytes,
        native_max_bytes=native_max_bytes,
        read_deadline_seconds=read_deadline_seconds,
    )


def _require_positive_config_int(config: ConfigProtocol, key: str) -> int:
    raw_value = config.get(key)
    error_message = f"{key} must be a positive integer."
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise ValidationError(error_message)
    return require_positive_int_strict(raw_value, error_message=error_message)
