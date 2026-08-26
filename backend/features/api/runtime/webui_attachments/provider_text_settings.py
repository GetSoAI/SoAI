"""SoAI - WebUI attachment provider text settings [backend/features/api/runtime/webui_attachments/provider_text_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_positive_int_strict,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "PROVIDER_TEXT_CHAR_TO_TOKEN_RATIO_KEY",
    "PROVIDER_TEXT_CONTEXT_FRACTION_KEY",
    "PROVIDER_TEXT_MAX_STORE_CHARS_KEY",
    "PROVIDER_TEXT_MIN_CHARS_KEY",
    "PROVIDER_TEXT_RESERVED_OUTPUT_TOKENS_KEY",
    "PROVIDER_TEXT_UPLOAD_PARSE_TIMEOUT_SEC_KEY",
    "ProviderTextSettings",
    "read_provider_text_settings",
)

PROVIDER_TEXT_MAX_STORE_CHARS_KEY = "SERVER.WEBUI.PROVIDER_TEXT.MAX_STORE_CHARS"
PROVIDER_TEXT_MIN_CHARS_KEY = "SERVER.WEBUI.PROVIDER_TEXT.MIN_CHARS"
PROVIDER_TEXT_CONTEXT_FRACTION_KEY = "SERVER.WEBUI.PROVIDER_TEXT.CONTEXT_FRACTION"
PROVIDER_TEXT_CHAR_TO_TOKEN_RATIO_KEY = "SERVER.WEBUI.PROVIDER_TEXT.CHAR_TO_TOKEN_RATIO"
PROVIDER_TEXT_RESERVED_OUTPUT_TOKENS_KEY = "SERVER.WEBUI.PROVIDER_TEXT.RESERVED_OUTPUT_TOKENS"
PROVIDER_TEXT_UPLOAD_PARSE_TIMEOUT_SEC_KEY = "SERVER.WEBUI.PROVIDER_TEXT.UPLOAD_PARSE_TIMEOUT_SEC"


@dataclass(frozen=True, slots=True)
class ProviderTextSettings:
    max_store_chars: int
    min_chars: int
    context_fraction: float
    char_to_token_ratio: int
    reserved_output_tokens: int
    upload_parse_timeout_sec: float


def _require_positive_float(value: float, *, key: str) -> float:
    if not math.isfinite(value) or value <= 0.0:
        raise ValidationError(f"{key} must be a positive finite number.")
    return value


def _require_fraction(value: float, *, key: str) -> float:
    if not math.isfinite(value) or value <= 0.0 or value > 1.0:
        raise ValidationError(f"{key} must be greater than 0 and less than or equal to 1.")
    return value


def read_provider_text_settings(config: ConfigProtocol) -> ProviderTextSettings:
    max_store_chars = require_positive_int_strict(
        config.get_int(PROVIDER_TEXT_MAX_STORE_CHARS_KEY),
        error_message=f"{PROVIDER_TEXT_MAX_STORE_CHARS_KEY} must be a positive integer.",
    )
    min_chars = require_positive_int_strict(
        config.get_int(PROVIDER_TEXT_MIN_CHARS_KEY),
        error_message=f"{PROVIDER_TEXT_MIN_CHARS_KEY} must be a positive integer.",
    )
    if min_chars > max_store_chars:
        raise ValidationError(
            f"{PROVIDER_TEXT_MIN_CHARS_KEY} must be less than or equal to {PROVIDER_TEXT_MAX_STORE_CHARS_KEY}.",
        )
    return ProviderTextSettings(
        max_store_chars=max_store_chars,
        min_chars=min_chars,
        context_fraction=_require_fraction(
            config.get_float(PROVIDER_TEXT_CONTEXT_FRACTION_KEY),
            key=PROVIDER_TEXT_CONTEXT_FRACTION_KEY,
        ),
        char_to_token_ratio=require_positive_int_strict(
            config.get_int(PROVIDER_TEXT_CHAR_TO_TOKEN_RATIO_KEY),
            error_message=f"{PROVIDER_TEXT_CHAR_TO_TOKEN_RATIO_KEY} must be a positive integer.",
        ),
        reserved_output_tokens=require_non_negative_int_strict(
            config.get_int(PROVIDER_TEXT_RESERVED_OUTPUT_TOKENS_KEY),
            error_message=(
                f"{PROVIDER_TEXT_RESERVED_OUTPUT_TOKENS_KEY} must be a non-negative integer."
            ),
        ),
        upload_parse_timeout_sec=_require_positive_float(
            config.get_float(PROVIDER_TEXT_UPLOAD_PARSE_TIMEOUT_SEC_KEY),
            key=PROVIDER_TEXT_UPLOAD_PARSE_TIMEOUT_SEC_KEY,
        ),
    )
