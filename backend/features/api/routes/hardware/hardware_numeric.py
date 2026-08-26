"""SoAI - Numeric coercion helpers for hardware routes [backend/features/api/routes/hardware/hardware_numeric.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math

from core.logging.trace import get_logger
from core.types.json import JSONValue
from core.validation.numbers import coerce_float_from_json

__all__ = ("safe_numeric",)

LOGGER_NAME = "SoAI.features.api.hardware_numeric"


def safe_numeric(
    value: JSONValue,
    field_name: str,
    default: float | None = None,
    secondary: JSONValue = None,
) -> float | None:
    parsed_value = _coerce_candidate_numeric(value, field_name=field_name, label="numeric")
    if parsed_value is not None:
        return parsed_value
    parsed_default = _coerce_candidate_numeric(default, field_name=field_name, label="default")
    if parsed_default is not None:
        return parsed_default
    parsed_secondary = _coerce_candidate_numeric(
        secondary,
        field_name=field_name,
        label="secondary",
    )
    if parsed_secondary is not None:
        return parsed_secondary
    return None


def _coerce_candidate_numeric(
    candidate: JSONValue,
    *,
    field_name: str,
    label: str,
) -> float | None:
    parsed = coerce_float_from_json(
        candidate,
        default=None,
        allow_bool=False,
        allow_nonfinite=False,
    )
    if parsed is not None:
        return parsed
    if candidate is None or isinstance(candidate, bool):
        return None
    logger = get_logger(LOGGER_NAME)
    if isinstance(candidate, int | float) and not math.isfinite(float(candidate)):
        logger.debug("Non-finite %s value for %s: %s", label, field_name, candidate)
        return None
    logger.debug("Failed to parse %s value for %s: %s", label, field_name, candidate)
    return None
