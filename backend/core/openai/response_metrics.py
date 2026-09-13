"""SoAI - Validated OpenAI response performance metrics [backend/core/openai/response_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.errors.exceptions import ModelOutputContractError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("parse_response_metrics",)


def parse_response_metrics(value: JSONValue) -> JSONDict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ModelOutputContractError("The model returned invalid performance metrics.")
    metrics: JSONDict = {}
    for field, measurement in value.items():
        if field == "speculative_decoding":
            metrics[field] = _parse_speculative_metrics(measurement)
        elif field in (
            "time_to_first_token_ms",
            "generation_time_ms",
            "queue_time_ms",
            "mean_itl_ms",
            "tokens_per_second",
        ):
            metrics[field] = _nonnegative_measurement(measurement)
        else:
            raise ModelOutputContractError("The model returned unsupported performance metrics.")
    return metrics


def _nonnegative_measurement(value: JSONValue) -> int | float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or isinstance(value, float)
        and not math.isfinite(value)
        or value < 0
    ):
        raise ModelOutputContractError("The model returned invalid performance metrics.")
    return value


def _parse_speculative_metrics(value: JSONValue) -> JSONDict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ModelOutputContractError("The model returned invalid speculative decoding metrics.")
    metrics: JSONDict = {}
    for field, measurement in value.items():
        if field in ("acceptance_histogram", "per_step_accepted", "per_step_drafted"):
            if measurement is None and field != "acceptance_histogram":
                metrics[field] = None
                continue
            if not isinstance(measurement, list) or any(
                not isinstance(item, int) or isinstance(item, bool) or item < 0
                for item in measurement
            ):
                raise ModelOutputContractError(
                    "The model returned invalid speculative decoding metrics."
                )
            metrics[field] = list(measurement)
        elif field in (
            "mean_acceptance_length",
            "draft_acceptance_rate",
            "num_spec_steps",
            "num_accepted_draft_tokens",
            "num_draft_tokens",
            "num_spec_tokens",
        ):
            number = _nonnegative_measurement(measurement)
            if number is None or field.startswith("num_") and not isinstance(number, int):
                raise ModelOutputContractError(
                    "The model returned invalid speculative decoding metrics."
                )
            if field == "draft_acceptance_rate" and number > 1:
                raise ModelOutputContractError(
                    "The model returned invalid speculative decoding metrics."
                )
            metrics[field] = number
        else:
            raise ModelOutputContractError(
                "The model returned unsupported speculative decoding metrics."
            )
    return metrics
