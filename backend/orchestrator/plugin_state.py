"""SoAI - Orchestrator plugin state model [backend/orchestrator/plugin_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass, field

from core.types.json import JSONDict

__all__ = ("PluginState",)


@dataclass(slots=True)
class PluginState:
    plugin_name: str
    loaded_model_universal_id: str | None = None
    last_request_universal_id: str | None = None
    loaded_parameters: JSONDict | None = None
    parameter_version: int | None = None
    last_activity: float = field(default_factory=time.monotonic)
    is_busy: bool = False
    active_tasks: set[str] = field(default_factory=set[str])
    avg_processing_time_ema: float = 1.0
    model_load_time: float | None = None
    finalize_pending: bool = False
