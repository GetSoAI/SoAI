"""SoAI - Orchestrator configuration types [backend/orchestrator/config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.orchestrator.routing_config import RoutingConfig
from core.orchestrator.runtime_config import (
    OrchestratorRuntimeConfig,
    OrchestratorSizingConfig,
)
from core.validation.boolean_coercion import coerce_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_runtime_config",)

LOGGER_NAME = "SoAI.orchestrator.config"
_MIN_FREE_DISK_BYTES_FOR_ACCEPT_DEFAULT = 256 * MIB_BYTES


def _build_concurrency_config(
    concurrency_defaults: JSONDict,
    default_limit: int,
    logger: TraceLogger,
) -> JSONDict:
    per_plugin_limits = concurrency_defaults.get("PER_PLUGIN", {})
    normalized_per_plugin: JSONDict = {}
    if isinstance(per_plugin_limits, dict):
        for plugin_name_raw, plugin_limit_raw in per_plugin_limits.items():
            if not isinstance(plugin_name_raw, str):
                continue
            normalized_per_plugin[plugin_name_raw] = coerce_positive_int(
                plugin_limit_raw,
                default=default_limit,
                minimum=0,
                label=f"MAX_CONCURRENT_TASKS_PER_PLUGIN.PER_PLUGIN[{plugin_name_raw}]",
                logger=logger,
            )
    return {"DEFAULT": default_limit, "PER_PLUGIN": normalized_per_plugin}


def _build_orchestrator_sizing_config(
    health_check_config: JSONDict,
    logger: TraceLogger,
) -> OrchestratorSizingConfig:
    concurrency_defaults = health_check_config.get(
        "MAX_CONCURRENT_TASKS_PER_PLUGIN",
        {"DEFAULT": 4, "PER_PLUGIN": {}},
    )
    normalized_defaults: JSONDict = (
        dict(concurrency_defaults) if isinstance(concurrency_defaults, dict) else {}
    )
    concurrency_default_limit = coerce_positive_int(
        normalized_defaults.get("DEFAULT", 4),
        default=4,
        minimum=0,
        label="MAX_CONCURRENT_TASKS_PER_PLUGIN.DEFAULT",
        logger=logger,
    )
    return OrchestratorSizingConfig(
        num_planner_workers=coerce_positive_int(
            health_check_config.get("NUM_PLANNER_WORKERS", 16),
            default=16,
            minimum=1,
            maximum=256,
            label="MODELS.ROUTING.HEALTH_CHECKS.NUM_PLANNER_WORKERS",
            logger=logger,
        ),
        failover_cooldown=coerce_positive_float(
            health_check_config.get("VIRTUAL_MODEL_FAILOVER_COOLDOWN_SEC", 15.0),
            default=15.0,
            minimum=0.0,
            label="MODELS.ROUTING.HEALTH_CHECKS.VIRTUAL_MODEL_FAILOVER_COOLDOWN_SEC",
            logger=logger,
        ),
        max_recovery_attempts=coerce_positive_int(
            health_check_config.get("MAX_RECOVERY_ATTEMPTS", 3),
            default=3,
            minimum=0,
            maximum=100,
            label="MODELS.ROUTING.HEALTH_CHECKS.MAX_RECOVERY_ATTEMPTS",
            logger=logger,
        ),
        concurrency_config=_build_concurrency_config(
            concurrency_defaults=normalized_defaults,
            default_limit=concurrency_default_limit,
            logger=logger,
        ),
        fair_dispatch_enabled=coerce_bool(
            health_check_config.get("FAIR_DISPATCH_ENABLED", True),
            default=True,
        ),
        fair_dispatch_cap=coerce_positive_int(
            health_check_config.get("FAIR_DISPATCH_MAX_PER_PLUGIN", 32),
            default=32,
            maximum=10_000,
            label="MODELS.ROUTING.HEALTH_CHECKS.FAIR_DISPATCH_MAX_PER_PLUGIN",
            logger=logger,
        ),
        plugin_queue_burst_factor=coerce_positive_int(
            health_check_config.get("PLUGIN_QUEUE_BURST_FACTOR", 4),
            default=4,
            maximum=100,
            label="PLUGIN_QUEUE_BURST_FACTOR",
            logger=logger,
        ),
        plugin_queue_min_size=coerce_positive_int(
            health_check_config.get("PLUGIN_QUEUE_MIN_SIZE", 16),
            default=16,
            maximum=100_000,
            label="PLUGIN_QUEUE_MIN_SIZE",
            logger=logger,
        ),
        plugin_queue_unlimited_workers=coerce_positive_int(
            health_check_config.get("PLUGIN_QUEUE_UNLIMITED_WORKERS", 8),
            default=8,
            minimum=1,
            maximum=256,
            label="MODELS.ROUTING.HEALTH_CHECKS.PLUGIN_QUEUE_UNLIMITED_WORKERS",
            logger=logger,
        ),
        plugin_queue_max_workers=coerce_positive_int(
            health_check_config.get("PLUGIN_QUEUE_MAX_WORKERS", 32),
            default=32,
            minimum=1,
            maximum=1024,
            label="MODELS.ROUTING.HEALTH_CHECKS.PLUGIN_QUEUE_MAX_WORKERS",
            logger=logger,
        ),
    )


def build_runtime_config(
    routing_config: RoutingConfig,
    metrics: MetricsManagerProtocol,
) -> OrchestratorRuntimeConfig:
    logger = get_logger(LOGGER_NAME)
    health_check_config = routing_config.health_checks
    sizing_config = _build_orchestrator_sizing_config(
        health_check_config=health_check_config,
        logger=logger,
    )
    raw_billing_threshold = metrics.config.get(
        "OBSERVABILITY.METRICS.CONSERVATIVE_BILLING_CHAR_THRESHOLD",
        25,
    )
    return OrchestratorRuntimeConfig(
        task_queue_max_size=coerce_positive_int(
            routing_config.task_queue_max_size,
            default=1000,
            minimum=0,
            maximum=100_000,
            label="MODELS.ROUTING.TASK_QUEUE_MAX_SIZE",
            logger=logger,
        ),
        scheduler_safety_net_delay=coerce_positive_float(
            routing_config.scheduler_safety_net_delay_sec,
            default=0.5,
            label="MODELS.ROUTING.SCHEDULER_SAFETY_NET_DELAY_SEC",
            logger=logger,
        ),
        durable_queue_lease_ttl_sec=coerce_positive_float(
            routing_config.durable_queue_lease_ttl_sec,
            default=30.0,
            minimum=1.0,
            label="MODELS.ROUTING.DURABLE_QUEUE_LEASE_TTL_SEC",
            logger=logger,
        ),
        durable_queue_recovery_sweep_sec=coerce_positive_float(
            routing_config.durable_queue_recovery_sweep_sec,
            default=5.0,
            minimum=0.1,
            label="MODELS.ROUTING.DURABLE_QUEUE_RECOVERY_SWEEP_SEC",
            logger=logger,
        ),
        durable_queue_hard_limit_tasks=coerce_positive_int(
            routing_config.durable_queue_hard_limit_tasks,
            default=0,
            minimum=0,
            maximum=10_000_000,
            label="MODELS.ROUTING.DURABLE_QUEUE_HARD_LIMIT_TASKS",
            logger=logger,
        ),
        min_free_disk_bytes_for_accept=coerce_positive_int(
            routing_config.min_free_disk_bytes_for_accept,
            default=_MIN_FREE_DISK_BYTES_FOR_ACCEPT_DEFAULT,
            minimum=0,
            maximum=10_000_000_000_000,
            label="MODELS.ROUTING.MIN_FREE_DISK_BYTES_FOR_ACCEPT",
            logger=logger,
        ),
        cancel_on_client_disconnect=coerce_bool(
            routing_config.cancel_on_client_disconnect,
            default=False,
        ),
        http_async_accept_default=coerce_bool(
            routing_config.http_async_accept_default,
            default=False,
        ),
        acceptance_db_busy_timeout_sec=coerce_positive_float(
            routing_config.acceptance_db_busy_timeout_sec,
            default=30.0,
            minimum=0.0,
            label="MODELS.ROUTING.ACCEPTANCE_DB_BUSY_TIMEOUT_SEC",
            logger=logger,
        ),
        plugin_prefetch_window_default=coerce_positive_int(
            routing_config.plugin_prefetch_window_default,
            default=8,
            minimum=1,
            maximum=10_000,
            label="MODELS.ROUTING.PLUGIN_PREFETCH_WINDOW_DEFAULT",
            logger=logger,
        ),
        standard_priority_aging_sec=coerce_positive_float(
            routing_config.standard_priority_aging_sec,
            default=25.0,
            minimum=0.0,
            label="MODELS.ROUTING.STANDARD_PRIORITY_AGING_SEC",
            logger=logger,
        ),
        flex_priority_aging_sec=coerce_positive_float(
            routing_config.flex_priority_aging_sec,
            default=120.0,
            minimum=0.0,
            label="MODELS.ROUTING.FLEX_PRIORITY_AGING_SEC",
            logger=logger,
        ),
        health_check_config=health_check_config,
        num_planner_workers=sizing_config.num_planner_workers,
        max_concurrent_plugins=coerce_positive_int(
            routing_config.max_concurrent_plugins,
            default=0,
            minimum=0,
            maximum=1000,
            label="MODELS.ROUTING.MAX_CONCURRENT_PLUGINS",
            logger=logger,
        ),
        dedup_enabled=coerce_bool(routing_config.deduplication_enabled, default=False),
        prompt_queuing_enabled=coerce_bool(routing_config.prompt_queuing, default=False),
        queue_prompt_slot_limit=coerce_positive_int(
            routing_config.queue_prompt_slot_limit,
            default=4,
            minimum=1,
            maximum=1000,
            label="MODELS.ROUTING.QUEUE_PROMPT_SLOT_LIMIT",
            logger=logger,
        ),
        fair_task_rotation_enabled=coerce_bool(routing_config.fair_task_rotation, default=False),
        failover_cooldown=sizing_config.failover_cooldown,
        max_recovery_attempts=sizing_config.max_recovery_attempts,
        concurrency_config=sizing_config.concurrency_config,
        fair_dispatch_enabled=sizing_config.fair_dispatch_enabled,
        fair_dispatch_cap=sizing_config.fair_dispatch_cap,
        plugin_queue_burst_factor=sizing_config.plugin_queue_burst_factor,
        plugin_queue_min_size=sizing_config.plugin_queue_min_size,
        plugin_queue_unlimited_workers=sizing_config.plugin_queue_unlimited_workers,
        plugin_queue_max_workers=sizing_config.plugin_queue_max_workers,
        conservative_billing_threshold=coerce_positive_int(
            raw_billing_threshold,
            default=25,
            minimum=0,
            label="OBSERVABILITY.METRICS.CONSERVATIVE_BILLING_CHAR_THRESHOLD",
            logger=logger,
        ),
    )
