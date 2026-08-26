"""SoAI - Metrics rehydration value coercion and application [backend/metrics/manager/rehydration/value_application.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from core.validation.coercion import coerce_int
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from metrics.manager.types import MetricValue

    type MetricLabel = str
    type ParentMap = dict[str, MetricValue]

__all__ = ("apply_rehydrated_value",)


def _coerce_metric_value(value: JSONValue) -> MetricValue | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float | str):
        return value
    if isinstance(value, list):
        list_result: list[MetricValue] = []
        for entry in value:
            coerced = _coerce_metric_value(entry)
            if coerced is None:
                return None
            list_result.append(coerced)
        return list_result
    if isinstance(value, dict):
        dict_result: dict[str, MetricValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                return None
            coerced = _coerce_metric_value(item)
            if coerced is None:
                return None
            dict_result[key] = coerced
        return dict_result
    return None


def apply_rehydrated_value(
    parent: ParentMap,
    leaf: str,
    template: MetricValue,
    value: JSONValue,
) -> bool:
    if isinstance(template, deque):
        if isinstance(value, list | tuple | deque):
            items: list[float] = []
            for entry in value:
                if isinstance(entry, bool) or not isinstance(entry, int | float):
                    return False
                items.append(float(entry))
            parent[leaf] = deque(items, maxlen=template.maxlen)
            return True
        return False
    if isinstance(template, set):
        if isinstance(value, list | tuple | set):
            try:
                labels: set[str] = set()
                for entry in value:
                    if not isinstance(entry, str):
                        return False
                    if entry:
                        labels.add(entry)
                parent[leaf] = labels
            except TypeError:
                return False
            return True
        return False
    if isinstance(template, dict) and "items" in template and ("timestamps" in template):
        if not isinstance(value, dict):
            return False
        raw_items = value.get("items", [])
        if isinstance(raw_items, dict):
            raw_items_iterable = list(raw_items.keys())
        elif isinstance(raw_items, list | tuple | set):
            raw_items_iterable = list(raw_items)
        else:
            raw_items_iterable = [raw_items] if raw_items is not None else []
        items_set: set[MetricLabel] = set()
        for entry in raw_items_iterable:
            entry_text = entry if isinstance(entry, str) else str(entry)
            if entry_text:
                items_set.add(entry_text)
        raw_timestamps = value.get("timestamps", [])
        normalized_timestamps: deque[tuple[float, MetricLabel]] = deque()
        if isinstance(raw_timestamps, list | tuple | deque):
            for entry in raw_timestamps:
                label: JSONValue | None = None
                ts_candidate: JSONValue = entry
                if isinstance(entry, list | tuple):
                    if len(entry) >= 2:
                        ts_candidate, label = (entry[0], entry[1])
                    elif len(entry) == 1:
                        ts_candidate = entry[0]
                if label is None:
                    continue
                if not isinstance(ts_candidate, int | float | str):
                    continue
                try:
                    ts_value = float(ts_candidate)
                except (TypeError, ValueError):
                    continue
                label_text = label if isinstance(label, str) else str(label)
                if label_text:
                    normalized_timestamps.append((ts_value, label_text))
        counts_payload = value.get("counts")
        counts_map: dict[str, MetricValue] = {}
        if isinstance(counts_payload, dict):
            for key, raw_count in counts_payload.items():
                label_text = key if isinstance(key, str) else str(key)
                if not label_text:
                    continue
                count_int = coerce_int(raw_count)
                if count_int is None:
                    continue
                if count_int > 0:
                    counts_map[label_text] = count_int
        else:
            for _ts_value, label in normalized_timestamps:
                current = counts_map.get(label, 0)
                current_int = int(current) if is_strict_int(current) else 0
                counts_map[label] = current_int + 1
        template["items"] = set(counts_map.keys())
        template["timestamps"] = deque(normalized_timestamps)
        template["counts"] = counts_map
        return True
    coerced = _coerce_metric_value(value)
    if coerced is None:
        return False
    parent[leaf] = coerced
    return True
