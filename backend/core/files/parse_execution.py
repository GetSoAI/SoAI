"""SoAI - File parse execution controls [backend/core/files/parse_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.files.types import ParseExecutionContext

__all__ = (
    "raise_if_parse_cancelled",
    "report_parse_progress",
)


def raise_if_parse_cancelled(context: ParseExecutionContext) -> None:
    if context.cancellation_token is not None:
        context.cancellation_token.raise_if_cancelled()


async def report_parse_progress(
    context: ParseExecutionContext,
    value: float,
    stage: str,
) -> None:
    if context.progress_callback is not None:
        await context.progress_callback(value, stage)
