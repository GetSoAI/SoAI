"""SoAI - Metrics rehydration from record payloads [backend/metrics/manager/rehydration/records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.metrics.keyspace_base import (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_QUEUED,
    METRIC_KEY_REQUESTS,
    METRIC_KEY_TOTAL,
)
from core.serialization.json_parsing import parse_json_value
from core.types.json import is_json_value
from metrics.manager.rehydration.key_paths import (
    locate_metric_entry,
    smart_split_metric_key,
)
from metrics.manager.rehydration.value_application import apply_rehydrated_value

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from metrics.manager.types import MetricsTree, MetricValue

__all__ = ("rehydrate_metrics_from_records",)

LOGGER_NAME = "SoAI.metrics.manager.records"
OPERATION = "metrics_manager.rehydrate_metrics_from_records"


def _read_non_negative_counter(value: MetricValue | None) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if value < 0:
        return None
    return int(value)


def _seed_director_request_total(metrics: MetricsTree) -> bool:
    director = metrics.get(METRIC_BLOCK_DIRECTOR)
    if not isinstance(director, dict):
        return False
    requests_dict = director.get(METRIC_KEY_REQUESTS)
    if not isinstance(requests_dict, dict):
        return False
    queued = _read_non_negative_counter(requests_dict.get(METRIC_KEY_QUEUED))
    if queued is None:
        return False
    total = _read_non_negative_counter(requests_dict.get(METRIC_KEY_TOTAL))
    if total is not None and total >= queued:
        return False
    requests_dict[METRIC_KEY_TOTAL] = queued
    return True


def rehydrate_metrics_from_records(
    records: list[JSONDict],
    metrics: MetricsTree,
) -> int:
    logger = get_logger(LOGGER_NAME)
    rehydrated_count = 0
    for record in records:
        metric_key_raw = record.get("metric_key")
        str_value = record.get("value")
        if not isinstance(metric_key_raw, str):
            continue
        metric_key = metric_key_raw
        if isinstance(metric_key, str) and metric_key.startswith("genesis."):
            continue
        try:
            parsed = parse_json_value(str_value) if isinstance(str_value, str) else None
        except (ValidationError, TypeError) as exception:
            log_exception(
                logger,
                exception,
                message="Could not decode metric value during rehydration",
                operation=OPERATION,
                details={"metric_key": metric_key},
                level="warning",
            )
            continue
        if not is_json_value(parsed):
            continue
        value: JSONValue = parsed
        keys_tuple = smart_split_metric_key(metric_key, metrics)
        if keys_tuple is None:
            logger.warning(
                "Could not find a valid rehydration path for metric key '%s'. Skipping.",
                metric_key,
            )
            continue
        located = locate_metric_entry(keys_tuple, metric_key, metrics)
        if not located:
            logger.warning(
                "Could not find a valid rehydration path for metric key '%s'. Skipping.",
                metric_key,
            )
            continue
        parent, leaf, template = located
        if apply_rehydrated_value(parent, leaf, template, value):
            rehydrated_count += 1
        else:
            logger.warning(
                "Persisted value for '%s' is incompatible with the current metrics structure. Skipping.",
                metric_key,
            )
    if _seed_director_request_total(metrics):
        rehydrated_count += 1
    return rehydrated_count
