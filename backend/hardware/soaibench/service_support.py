"""SoAI - SoAIBench service response helpers [backend/hardware/soaibench/service_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.hardware.soaibench_limits import (
    SOAIBENCH_LIST_MAX_LIMIT,
    SOAIBENCH_LIST_MIN_LIMIT,
)
from core.validation.numbers import coerce_int_clamped_with_default
from hardware.soaibench.errors import unsupported_guidance
from hardware.soaibench.responses import run_response
from hardware.soaibench.types import SoAIBenchRunStatus

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("limit_or_default", "unsupported_response")


def unsupported_response(
    *,
    device_id: str,
    profile: str | None,
    reason: str,
    message: str,
) -> JSONDict:
    return run_response(
        {
            "device_id": device_id,
            "profile": profile,
            "status": SoAIBenchRunStatus.UNSUPPORTED.value,
            "unsupported_reason": reason,
            "summary": {
                "message": message,
                "guidance": unsupported_guidance(reason),
            },
        },
        accepted=False,
        history=[],
    )


def limit_or_default(value: int, *, default: int) -> int:
    return coerce_int_clamped_with_default(
        value,
        default=default,
        fallback=default,
        minimum=SOAIBENCH_LIST_MIN_LIMIT,
        maximum=SOAIBENCH_LIST_MAX_LIMIT,
    )
