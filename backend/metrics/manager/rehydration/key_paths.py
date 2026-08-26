"""SoAI - Metrics rehydration key path resolution [backend/metrics/manager/rehydration/key_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING, TypeGuard

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from metrics.manager.types import MetricsTree, MetricValue

    type MetricKeyPath = tuple[str, ...]
    type MetricDefaultDict = defaultdict[str, MetricValue]
    type ParentMap = dict[str, MetricValue]

__all__ = (
    "locate_metric_entry",
    "smart_split_metric_key",
)

LOGGER_NAME = "SoAI.metrics.manager.key_paths"
OPERATION_METRICS_MANAGER_LOCATE_METRIC_ENTRY = "metrics_manager.locate_metric_entry"
OPERATION_METRICS_MANAGER_SMART_SPLIT_METRIC_KEY = "metrics_manager.smart_split_metric_key"
OPERATION_METRICS_MANAGER_SMART_SPLIT_METRIC_KEY_MATCHES_TEMPLATE = (
    "metrics_manager.smart_split_metric_key.matches_template"
)


def _is_metric_defaultdict(value: MetricValue) -> TypeGuard[MetricDefaultDict]:
    return isinstance(value, defaultdict)


def _is_metric_mapping(value: MetricValue) -> TypeGuard[dict[str, MetricValue]]:
    return isinstance(value, dict)


def smart_split_metric_key(
    metric_key: str,
    metrics: MetricsTree,
) -> MetricKeyPath | None:
    logger = get_logger(LOGGER_NAME)
    cleaned = str(metric_key or "").strip()
    if not cleaned:
        return None

    def _is_leaf_template_value(value: MetricValue) -> bool:
        if isinstance(value, bool | int | float | str | deque | set | list):
            return True
        if isinstance(value, dict) and "items" in value and ("timestamps" in value):
            return True
        return False

    def _matches_template(template: MetricValue, parts: list[str]) -> bool:
        if not parts:
            return False
        current: MetricValue = template
        for index, part in enumerate(parts):
            last = index == len(parts) - 1
            if _is_metric_defaultdict(current):
                default_factory = current.default_factory
                if default_factory is None:
                    return False
                try:
                    template_value: MetricValue = default_factory()
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Metrics template default_factory failed during rehydration match (non-critical).",
                        operation=OPERATION_METRICS_MANAGER_SMART_SPLIT_METRIC_KEY_MATCHES_TEMPLATE,
                        details={"metric_key": metric_key},
                        level="debug",
                    )
                    return False
                if last:
                    if _is_metric_mapping(template_value):
                        return False
                    return _is_leaf_template_value(template_value)
                current = template_value
                continue
            if _is_metric_mapping(current):
                if part not in current:
                    return False
                value = current[part]
                if last:
                    return _is_leaf_template_value(value)
                current = value
                continue
            return False
        return False

    parts = [segment for segment in cleaned.split(".") if segment]
    current: MetricValue = metrics
    result_keys: list[str] = []
    index = 0
    while index < len(parts):
        part = parts[index]
        if _is_metric_defaultdict(current):
            remaining_parts = parts[index:]
            default_factory = current.default_factory
            template: MetricValue | None = None
            if default_factory is not None:
                try:
                    template = default_factory()
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Metrics template default_factory failed during smart key split (non-critical).",
                        operation=OPERATION_METRICS_MANAGER_SMART_SPLIT_METRIC_KEY,
                        details={"metric_key": metric_key},
                        level="debug",
                    )
                    template = None
            if template is None:
                return None
            if len(remaining_parts) == 1:
                if _is_metric_mapping(template):
                    return None
                result_keys.append(remaining_parts[0])
                return tuple(result_keys)
            split_index: int | None = None
            if _is_metric_mapping(template):
                for offset in range(1, len(remaining_parts)):
                    if _matches_template(template, remaining_parts[offset:]):
                        split_index = offset
                        break
            if split_index is None:
                if _is_metric_mapping(template):
                    return None
                result_keys.append(".".join(remaining_parts))
                return tuple(result_keys)
            result_keys.append(".".join(remaining_parts[:split_index]))
            current = template
            index += split_index
            continue
        if _is_metric_mapping(current):
            if part not in current:
                return None
            result_keys.append(part)
            current = current[part]
            index += 1
            continue
        parent_key = result_keys[-1] if result_keys else "<root>"
        logger.warning(
            "Rehydration conflict for '%s': parent path is not a dictionary at key '%s'. Skipping.",
            metric_key,
            parent_key,
        )
        return None
    return tuple(result_keys) if result_keys else None


def locate_metric_entry(
    keys: MetricKeyPath,
    metric_key: str,
    metrics: MetricsTree,
) -> tuple[ParentMap, str, MetricValue] | None:
    logger = get_logger(LOGGER_NAME)
    current: MetricValue = metrics
    for index, key in enumerate(keys):
        is_last = index == len(keys) - 1
        if _is_metric_defaultdict(current):
            try:
                value = current[key]
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to access defaultdict path segment during rehydration",
                    operation=OPERATION_METRICS_MANAGER_LOCATE_METRIC_ENTRY,
                    details={"metric_key": metric_key, "path_segment": key},
                    level="warning",
                )
                return None
            if is_last:
                return (current, key, value)
            current = value
            continue
        if isinstance(current, dict):
            if key not in current:
                return None
            value = current[key]
            if is_last:
                return (current, key, value)
            current = value
            continue
        parent_key = keys[index - 1] if index > 0 else "<root>"
        logger.warning(
            "Rehydration conflict for '%s': parent path is not a dictionary at key '%s'. Skipping.",
            metric_key,
            parent_key,
        )
        return None
    return None
