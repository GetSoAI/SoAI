"""SoAI - Hardware history data loading helpers [backend/features/api/routes/hardware/hardware_history_data_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.hardware.protocols import HardwareManagerProtocol
from core.history.request.models import PreparedHistoryRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("load_hardware_history_data",)


async def load_hardware_history_data(
    *,
    hardware_manager: HardwareManagerProtocol,
    history_request: PreparedHistoryRequest,
    component: str,
    gpu_index: int | None,
    identifier: str | None,
) -> JSONDict:
    return await hardware_manager.get_historical_data(
        start_ts_ms=history_request.start_ts_ms,
        end_ts_ms=history_request.end_ts_ms,
        points=history_request.requested_points,
        interval_ms=history_request.resolution.interval_ms,
        aggregation=history_request.aggregation,
        component=component,
        gpu_index=gpu_index,
        identifier=identifier,
    )
