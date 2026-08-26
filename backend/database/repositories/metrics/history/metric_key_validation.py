"""SoAI - Metrics history metric_key validation [backend/database/repositories/metrics/history/metric_key_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.errors.exceptions import ValidationError
from database.core.query_execution import query_one_to_dict

__all__ = ("require_metric_key_exists",)


async def require_metric_key_exists(database: aiosqlite.Connection, metric_key: str) -> None:
    row = await query_one_to_dict(
        database,
        "SELECT 1 FROM metrics_history WHERE metric_key = ? LIMIT 1",
        (metric_key,),
    )
    if row is None:
        raise ValidationError(f"Unknown metric_key '{metric_key}'")
