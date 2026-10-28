"""SoAI - NVIDIA SMI CSV value parsing [backend/hardware/vendors/nvidia/smi_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import csv
import io
import math
from typing import TYPE_CHECKING

from core.validation.text_numbers import coerce_float_from_text

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger

__all__ = (
    "parse_smi_csv_rows",
    "parse_smi_int",
    "parse_smi_number",
)


def parse_smi_number(raw_value: str) -> float | None:
    normalized = raw_value.strip()
    if (not normalized) or normalized.lower() in {"[not supported]", "n/a", "not supported"}:
        return None
    value = coerce_float_from_text(normalized, default=None)
    return value if value is not None and math.isfinite(value) else None


def parse_smi_int(raw_value: str) -> int | None:
    numeric_value = parse_smi_number(raw_value)
    if numeric_value is None or numeric_value < 0 or not numeric_value.is_integer():
        return None
    parsed_value = int(numeric_value)
    return parsed_value


def parse_smi_csv_rows(stdout: str, *, field_count: int, logger: TraceLogger) -> list[list[str]]:
    rows: list[list[str]] = []
    csv_reader = csv.reader(io.StringIO(stdout), skipinitialspace=True)
    for raw_row in csv_reader:
        normalized_row = [value.strip() for value in raw_row]
        if not normalized_row or all(not value for value in normalized_row):
            continue
        if len(normalized_row) != field_count:
            logger.trace(
                "nvidia-smi returned %s fields, expected %s: %s",
                len(normalized_row),
                field_count,
                normalized_row,
            )
            continue
        rows.append(normalized_row)
    return rows
