"""SoAI - Orchestrator runtime configuration model [backend/core/orchestrator/runtime_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "OrchestratorRuntimeConfig",
    "OrchestratorSizingConfig",
)


@dataclass(frozen=True, slots=True)
class OrchestratorSizingConfig:
    num_planner_workers: int
    failover_cooldown: float
    max_recovery_attempts: int
    concurrency_config: JSONDict
    fair_dispatch_enabled: bool
    fair_dispatch_cap: int
    plugin_queue_burst_factor: int
    plugin_queue_min_size: int
    plugin_queue_unlimited_workers: int
    plugin_queue_max_workers: int


@dataclass(frozen=True, slots=True)
class OrchestratorRuntimeConfig:
    task_queue_max_size: int
    scheduler_safety_net_delay: float
    durable_queue_lease_ttl_sec: float
    durable_queue_recovery_sweep_sec: float
    durable_queue_hard_limit_tasks: int
    min_free_disk_bytes_for_accept: int
    cancel_on_client_disconnect: bool
    http_async_accept_default: bool
    acceptance_db_busy_timeout_sec: float
    plugin_prefetch_window_default: int
    standard_priority_aging_sec: float
    flex_priority_aging_sec: float
    health_check_config: JSONDict
    num_planner_workers: int
    max_concurrent_plugins: int
    dedup_enabled: bool
    prompt_queuing_enabled: bool
    queue_prompt_slot_limit: int
    fair_task_rotation_enabled: bool
    failover_cooldown: float
    max_recovery_attempts: int
    concurrency_config: JSONDict
    fair_dispatch_enabled: bool
    fair_dispatch_cap: int
    plugin_queue_burst_factor: int
    plugin_queue_min_size: int
    plugin_queue_unlimited_workers: int
    plugin_queue_max_workers: int
    conservative_billing_threshold: int
