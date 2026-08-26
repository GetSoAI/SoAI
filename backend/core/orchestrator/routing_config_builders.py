"""SoAI - Routing configuration builder functions [backend/core/orchestrator/routing_config_builders.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.errors.exceptions import ValidationError
from core.logging.protocols import LoggerProtocol
from core.orchestrator.routing_config import RoutingConfig
from core.orchestrator.virtual_model_config_builders import (
    build_failover_configs,
    build_virtual_model_configs,
    coerce_virtual_model,
)
from core.validation.boolean_coercion import coerce_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_routing_config",
    "coerce_virtual_model",
)

_MIN_FREE_DISK_BYTES_FOR_ACCEPT_DEFAULT = 256 * MIB_BYTES


def build_routing_config(routing_section: JSONDict | None, logger: LoggerProtocol) -> RoutingConfig:
    source = dict(routing_section or {})
    source.pop("HTTP_CLIENT_LIMITS", None)
    source.pop("HTTP_CLIENT_TIMEOUTS", None)

    virtual_models = build_virtual_model_configs(source.pop("VIRTUAL_MODELS", []) or [], logger)
    failovers = build_failover_configs(source.pop("FAILOVERS", None), logger)

    max_concurrent = source.pop("MAX_CONCURRENT_PLUGINS", 2)
    task_queue_max = source.pop("TASK_QUEUE_MAX_SIZE", 1000)
    safety_net_delay = source.pop("SCHEDULER_SAFETY_NET_DELAY_SEC", 0.5)
    durable_queue_lease_ttl_sec = source.pop("DURABLE_QUEUE_LEASE_TTL_SEC", 30.0)
    durable_queue_recovery_sweep_sec = source.pop("DURABLE_QUEUE_RECOVERY_SWEEP_SEC", 5.0)
    durable_queue_hard_limit_tasks = source.pop("DURABLE_QUEUE_HARD_LIMIT_TASKS", 0)
    min_free_disk_bytes_for_accept = source.pop(
        "MIN_FREE_DISK_BYTES_FOR_ACCEPT",
        _MIN_FREE_DISK_BYTES_FOR_ACCEPT_DEFAULT,
    )
    plugin_prefetch_window_default = source.pop("PLUGIN_PREFETCH_WINDOW_DEFAULT", 8)
    standard_priority_aging_sec = source.pop("STANDARD_PRIORITY_AGING_SEC", 25.0)
    flex_priority_aging_sec = source.pop("FLEX_PRIORITY_AGING_SEC", 120.0)
    cancel_on_client_disconnect = source.pop("CANCEL_ON_CLIENT_DISCONNECT", False)
    http_async_accept_default = source.pop("HTTP_ASYNC_ACCEPT_DEFAULT", False)
    acceptance_db_busy_timeout_sec = source.pop("ACCEPTANCE_DB_BUSY_TIMEOUT_SEC", 30.0)
    inference_task_retention_days = source.pop("INFERENCE_TASK_RETENTION_DAYS", 180)
    owner_running_limits_raw = source.pop("OWNER_RUNNING_LIMITS", None)
    owner_running_limits_default, owner_running_limits_by_owner_type = build_owner_running_limits(
        owner_running_limits_raw,
        logger=logger,
    )
    dedup_enabled = source.pop("DEDUPLICATION_ENABLED", True)
    prompt_queueing = source.pop("PROMPT_QUEUING", False)
    queue_prompt_slot_limit = source.pop("QUEUE_PROMPT_SLOT_LIMIT", 4)
    fair_rotation = source.pop("FAIR_TASK_ROTATION", False)
    deduplication_keys_raw = source.pop("DEDUPLICATION_KEYS", []) or []
    deduplication_keys_list: list[str] = []
    if isinstance(deduplication_keys_raw, list):
        for raw_key in deduplication_keys_raw:
            if not isinstance(raw_key, str):
                continue
            key = raw_key.strip()
            if key:
                deduplication_keys_list.append(key)
    elif deduplication_keys_raw:
        logger.warning("Ignoring invalid routing DEDUPLICATION_KEYS (expected list of strings).")
    health_checks_raw = source.pop("HEALTH_CHECKS", None)
    return RoutingConfig(
        max_concurrent_plugins=coerce_positive_int(
            max_concurrent,
            default=2,
            label="MAX_CONCURRENT_PLUGINS",
            logger=logger,
        ),
        task_queue_max_size=coerce_positive_int(
            task_queue_max,
            default=1000,
            label="TASK_QUEUE_MAX_SIZE",
            logger=logger,
        ),
        scheduler_safety_net_delay_sec=coerce_positive_float(
            safety_net_delay,
            default=0.5,
            label="SCHEDULER_SAFETY_NET_DELAY_SEC",
            logger=logger,
        ),
        durable_queue_lease_ttl_sec=coerce_positive_float(
            durable_queue_lease_ttl_sec,
            default=30.0,
            minimum=1.0,
            label="DURABLE_QUEUE_LEASE_TTL_SEC",
            logger=logger,
        ),
        durable_queue_recovery_sweep_sec=coerce_positive_float(
            durable_queue_recovery_sweep_sec,
            default=5.0,
            minimum=0.1,
            label="DURABLE_QUEUE_RECOVERY_SWEEP_SEC",
            logger=logger,
        ),
        durable_queue_hard_limit_tasks=coerce_positive_int(
            durable_queue_hard_limit_tasks,
            default=0,
            minimum=0,
            label="DURABLE_QUEUE_HARD_LIMIT_TASKS",
            logger=logger,
        ),
        min_free_disk_bytes_for_accept=coerce_positive_int(
            min_free_disk_bytes_for_accept,
            default=_MIN_FREE_DISK_BYTES_FOR_ACCEPT_DEFAULT,
            minimum=0,
            label="MIN_FREE_DISK_BYTES_FOR_ACCEPT",
            logger=logger,
        ),
        plugin_prefetch_window_default=coerce_positive_int(
            plugin_prefetch_window_default,
            default=8,
            minimum=1,
            label="PLUGIN_PREFETCH_WINDOW_DEFAULT",
            logger=logger,
        ),
        standard_priority_aging_sec=coerce_positive_float(
            standard_priority_aging_sec,
            default=25.0,
            minimum=0.0,
            label="STANDARD_PRIORITY_AGING_SEC",
            logger=logger,
        ),
        flex_priority_aging_sec=coerce_positive_float(
            flex_priority_aging_sec,
            default=120.0,
            minimum=0.0,
            label="FLEX_PRIORITY_AGING_SEC",
            logger=logger,
        ),
        cancel_on_client_disconnect=coerce_bool(cancel_on_client_disconnect, default=False),
        http_async_accept_default=coerce_bool(http_async_accept_default, default=False),
        acceptance_db_busy_timeout_sec=coerce_positive_float(
            acceptance_db_busy_timeout_sec,
            default=30.0,
            minimum=0.0,
            label="ACCEPTANCE_DB_BUSY_TIMEOUT_SEC",
            logger=logger,
        ),
        inference_task_retention_days=coerce_positive_int(
            inference_task_retention_days,
            default=180,
            minimum=0,
            label="INFERENCE_TASK_RETENTION_DAYS",
            logger=logger,
        ),
        owner_running_limits_default=owner_running_limits_default,
        owner_running_limits_by_owner_type=owner_running_limits_by_owner_type,
        deduplication_enabled=coerce_bool(dedup_enabled, default=True),
        deduplication_keys=tuple(deduplication_keys_list),
        prompt_queuing=coerce_bool(prompt_queueing, default=False),
        queue_prompt_slot_limit=coerce_positive_int(
            queue_prompt_slot_limit,
            default=4,
            label="QUEUE_PROMPT_SLOT_LIMIT",
            logger=logger,
        ),
        fair_task_rotation=coerce_bool(fair_rotation, default=False),
        virtual_models=virtual_models,
        failovers=failovers,
        health_checks=build_health_checks(health_checks_raw),
    )


def build_health_checks(health_checks_raw: JSONValue) -> JSONDict:
    default_health_checks = RoutingConfig().health_checks
    if not health_checks_raw or not isinstance(health_checks_raw, dict):
        return default_health_checks
    merged: JSONDict = dict(default_health_checks)
    for key, value in health_checks_raw.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, str | int | float | bool | type(None)):
            merged[key] = value
        elif isinstance(value, dict):
            existing = merged.get(key)
            if isinstance(existing, dict):
                merged[key] = {**existing, **value}
            else:
                merged[key] = value
        elif isinstance(value, list):
            merged[key] = value
        else:
            merged[key] = str(value)
    return merged


def build_owner_running_limits(
    owner_running_limits_raw: JSONValue,
    *,
    logger: LoggerProtocol,
) -> tuple[int, dict[str, int]]:
    default_limit = 4
    per_owner_type: dict[str, int] = {}
    if owner_running_limits_raw is None:
        return (default_limit, per_owner_type)
    if not isinstance(owner_running_limits_raw, dict):
        logger.warning("Ignoring invalid routing OWNER_RUNNING_LIMITS (expected mapping).")
        return (default_limit, per_owner_type)
    default_raw = owner_running_limits_raw.get("DEFAULT", default_limit)
    default_limit = coerce_positive_int(
        default_raw,
        default=default_limit,
        minimum=0,
        label="OWNER_RUNNING_LIMITS.DEFAULT",
        logger=logger,
    )
    per_owner_type_raw = owner_running_limits_raw.get("PER_OWNER_TYPE", {}) or {}
    if not isinstance(per_owner_type_raw, dict):
        if per_owner_type_raw:
            logger.warning(
                "Ignoring invalid routing OWNER_RUNNING_LIMITS.PER_OWNER_TYPE (expected mapping).",
            )
        return (default_limit, per_owner_type)
    for key, value in per_owner_type_raw.items():
        if not isinstance(key, str):
            continue
        owner_type = key.strip()
        if not owner_type:
            continue
        try:
            limit = coerce_positive_int(
                value,
                default=default_limit,
                minimum=0,
                label=f"OWNER_RUNNING_LIMITS.PER_OWNER_TYPE.{owner_type}",
                logger=logger,
            )
        except (TypeError, ValidationError, ValueError):
            logger.warning(
                "Ignoring invalid routing OWNER_RUNNING_LIMITS.PER_OWNER_TYPE entry for '%s'.",
                owner_type,
            )
            continue
        per_owner_type[owner_type] = limit
    return (default_limit, per_owner_type)
