"""SoAI - GPU tuning dirty flag tracking [backend/hardware/gpu_tuning/dirty_tracking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

from hardware.gpu_tuning.backend_apply_results import gpu_apply_result_changed
from hardware.presets.slot_mutations import touch_dirty_flag

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONValue

__all__ = ("touch_dirty_flag_if_apply_changed",)


async def touch_dirty_flag_if_apply_changed(
    apply_result: Mapping[str, JSONValue],
    dirty_flag_path: str,
    logger: TraceLogger,
) -> None:
    if not gpu_apply_result_changed(apply_result):
        return
    await asyncio.to_thread(
        touch_dirty_flag,
        dirty_flag_path=dirty_flag_path,
        logger=logger,
    )
