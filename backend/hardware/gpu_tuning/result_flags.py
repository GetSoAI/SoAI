"""SoAI - GPU tuning operation result flag parsing [backend/hardware/gpu_tuning/result_flags.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.boolean_coercion import coerce_success_flag

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.logging.protocols import TraceLogger
    from core.types.json import JSONValue

__all__ = ("is_success_result",)


def is_success_result(
    result: Mapping[str, JSONValue],
    *,
    logger: TraceLogger,
    operation: str,
    recover_message: str | None = None,
) -> bool:
    return coerce_success_flag(
        result,
        "success",
        logger=logger,
        operation=operation,
        default=False,
        recover_message=recover_message,
    )
