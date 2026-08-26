"""SoAI - API quota reservation decision parsing [backend/features/api/runtime/quota_reservation_decisions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "QuotaReservationDecision",
    "parse_quota_reservation_decision",
)


@dataclass(frozen=True, slots=True)
class QuotaReservationDecision:
    allowed: bool
    reservation: JSONDict | None
    status: JSONDict | None
    window: str
    retry_at_ms: int


def parse_quota_reservation_decision(
    result: JSONDict,
    *,
    now_ts_ms: int,
) -> QuotaReservationDecision:
    allowed_value = result.get("allowed")
    allowed = allowed_value if isinstance(allowed_value, bool) else False
    reservation = coerce_json_dict(result.get("reservation"))
    status = coerce_json_dict(result.get("status"))
    window_value = result.get("window")
    window = window_value if isinstance(window_value, str) and window_value else "unknown"
    retry_at_value = result.get("retry_at_ms")
    if not is_strict_int(retry_at_value):
        retry_at_value = result.get("retry_at")
    retry_at_ms = int(retry_at_value) if is_strict_int(retry_at_value) else int(now_ts_ms)
    return QuotaReservationDecision(
        allowed=allowed,
        reservation=reservation,
        status=status,
        window=window,
        retry_at_ms=retry_at_ms,
    )
