"""SoAI - Plugin queue capacity calculation rules [backend/orchestrator/capacity/plugin_queue/capacity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.validation.integers import is_strict_int

__all__ = ("calculate_plugin_queue_capacity",)


def calculate_plugin_queue_capacity(
    *,
    config: OrchestratorRuntimeConfig,
    plugin_limit: int,
    plugin_count: int,
) -> int:
    resolved_plugin_limit = plugin_limit if is_strict_int(plugin_limit) and plugin_limit >= 0 else 0
    task_queue_max_size = config.task_queue_max_size
    if is_strict_int(task_queue_max_size):
        if task_queue_max_size == 0:
            return 0
        global_budget = task_queue_max_size if task_queue_max_size > 0 else 1024
    else:
        global_budget = 1024
    effective_budget = max(
        global_budget,
        config.plugin_queue_min_size,
    )
    effective_plugin_count = max(plugin_count, 1)
    per_plugin_share = max(effective_budget // effective_plugin_count, 1)
    burst_capacity = max(resolved_plugin_limit, 1) * config.plugin_queue_burst_factor
    capacity = max(config.plugin_queue_min_size, per_plugin_share, burst_capacity)
    return min(capacity, effective_budget)
