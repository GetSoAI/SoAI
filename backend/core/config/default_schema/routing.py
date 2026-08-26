"""SoAI - Default config schema: routing [backend/core/config/default_schema/routing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.byte_sizes import mib_to_bytes

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_routing_defaults",)


def build_routing_defaults() -> ConfigDict:
    return {
        "ROUTING": {
            "MAX_CONCURRENT_PLUGINS": 2,
            "TASK_QUEUE_MAX_SIZE": 1000,
            "SCHEDULER_SAFETY_NET_DELAY_SEC": 0.5,
            "DURABLE_QUEUE_LEASE_TTL_SEC": 30,
            "DURABLE_QUEUE_RECOVERY_SWEEP_SEC": 5,
            "DURABLE_QUEUE_HARD_LIMIT_TASKS": 0,
            "MIN_FREE_DISK_BYTES_FOR_ACCEPT": mib_to_bytes(256),
            "PLUGIN_PREFETCH_WINDOW_DEFAULT": 8,
            "STANDARD_PRIORITY_AGING_SEC": 25,
            "FLEX_PRIORITY_AGING_SEC": 120,
            "CANCEL_ON_CLIENT_DISCONNECT": False,
            "HTTP_ASYNC_ACCEPT_DEFAULT": False,
            "ACCEPTANCE_DB_BUSY_TIMEOUT_SEC": 30,
            "INFERENCE_TASK_RETENTION_DAYS": 180,
            "OWNER_RUNNING_LIMITS": {
                "DEFAULT": 4,
                "PER_OWNER_TYPE": {},
            },
            "DEDUPLICATION_ENABLED": True,
            "PROMPT_QUEUING": False,
            "FAIR_TASK_ROTATION": False,
            "DEDUPLICATION_KEYS": [],
            "FAILOVERS": [],
            "VIRTUAL_MODELS": [],
            "HTTP_CLIENT_TRUST_ENV": False,
            "HTTP_CLIENT_LIMITS": {
                "MAX_CONNECTIONS": 200,
                "MAX_KEEPALIVE_CONNECTIONS": 50,
            },
            "HTTP_CLIENT_TIMEOUTS": {
                "CONNECT": 30.0,
                "READ": 300.0,
                "WRITE": 60.0,
                "POOL": 30.0,
            },
            "HEALTH_CHECKS": {
                "INTERVAL_SEC": 20,
                "JITTER_FRACTION": 0.1,
                "STREAMING_IDLE_TIMEOUT_SEC": 300.0,
                "NON_STREAMING_TIMEOUT_SEC": 300.0,
                "STREAMING_PREFILL_MIN_TOKENS_PER_SEC": 50.0,
                "STREAMING_PREFILL_OVERHEAD_SEC": 60.0,
                "PING_TIMEOUT_SEC": 15,
                "STUCK_STATE_TIMEOUT_SEC": 900,
                "FLAPPING_WINDOW_SEC": 120,
                "FLAPPING_MIN_TRANSITIONS": 3,
                "IDLE_PING_GRACE_PERIOD_SEC": 5,
                "PENDING_STARTUP_TASK_TIMEOUT_SEC": 300,
                "FAILURE_THRESHOLD": 3,
                "RECOVERY_TIMEOUT_SEC": 1440,
                "FAILURE_WINDOW_SEC": 1440,
                "MAX_RECOVERY_ATTEMPTS": 3,
                "NUM_PLANNER_WORKERS": 16,
                "FAIR_DISPATCH_ENABLED": True,
                "FAIR_DISPATCH_MAX_PER_PLUGIN": 32,
                "PLUGIN_QUEUE_BURST_FACTOR": 4,
                "PLUGIN_QUEUE_MIN_SIZE": 16,
                "PLUGIN_QUEUE_UNLIMITED_WORKERS": 8,
                "PLUGIN_QUEUE_MAX_WORKERS": 32,
                "VIRTUAL_MODEL_FAILOVER_COOLDOWN_SEC": 15,
                "MAX_CONCURRENT_TASKS_PER_PLUGIN": {
                    "DEFAULT": 4,
                    "PER_PLUGIN": {},
                },
                "COMMAND_TIMEOUTS_SEC": {
                    "PLUGIN_STOP": 300,
                    "PLUGIN_LOAD_MODEL": 7200,
                },
            },
        },
    }
