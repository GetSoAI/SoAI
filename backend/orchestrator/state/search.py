"""SoAI - Orchestrator state search across plugins, models, and devices [backend/orchestrator/state/search.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from core.logging.protocols import TraceLogger
from core.types.json_value import copy_json_dict, copy_json_dict_list_map
from orchestrator.state.search_devices import (
    resolve_device_search_result,
    resolve_device_search_text,
    search_devices_candidates,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "empty_search_result",
    "perform_search",
    "prepare_search_inputs",
)

_NON_ALPHANUM_PATTERN = r"[^a-z0-9\s]"
_WHITESPACE_PATTERN = r"\s+"


def empty_search_result() -> dict[str, list[JSONDict]]:
    return {"plugins": [], "models": [], "devices": []}


def _normalize_search_string(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(
        _WHITESPACE_PATTERN,
        " ",
        re.sub(_NON_ALPHANUM_PATTERN, " ", text.lower()),
    ).strip()


def _matches_all_words(target_text: str, word_regexes: list[re.Pattern[str]]) -> bool:
    normalized_target = _normalize_search_string(target_text)
    return all(word_re.search(normalized_target) for word_re in word_regexes)


def _string_field(value: JSONValue | None, default: str = "") -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return default


def _filter_sequence[T](
    items: Iterable[T],
    word_regexes: list[re.Pattern[str]],
    limit: int,
    text_extraction_function: Callable[[T], str],
    result_transformation_function: Callable[[T], JSONDict],
) -> list[JSONDict]:
    filtered: list[JSONDict] = []
    for item in items:
        if len(filtered) >= limit:
            break
        if _matches_all_words(text_extraction_function(item), word_regexes):
            filtered.append(result_transformation_function(item))
    return filtered


def _search_plugins(
    plugins: Iterable[JSONDict] | None,
    word_regexes: list[re.Pattern[str]],
    limit: int,
) -> list[JSONDict]:
    if not plugins:
        return []

    def plugin_text(data: JSONDict) -> str:
        if not isinstance(data, dict):
            return ""
        return f"{data.get('name', '')} {data.get('display_name', '')} {data.get('description_soaiplugin', '')}"

    def plugin_result(data: JSONDict) -> JSONDict:
        if not isinstance(data, dict):
            return {}

        name = _string_field(data.get("name"))
        return {
            "name": name,
            "display_name": _string_field(data.get("display_name"), name),
            "version_soaiplugin": _string_field(data.get("version_soaiplugin"), "0.0.0"),
            "state": _string_field(data.get("state"), "UNKNOWN"),
        }

    return _filter_sequence(plugins, word_regexes, limit, plugin_text, plugin_result)


def _search_models(
    categorized_models: dict[str, list[JSONDict]] | None,
    word_regexes: list[re.Pattern[str]],
    limit: int,
) -> list[JSONDict]:
    if not categorized_models:
        return []
    models = (model for cat_list in categorized_models.values() for model in cat_list)

    def model_text(data: JSONDict) -> str:
        if not isinstance(data, dict):
            return ""
        tags = data.get("tags") or []
        tags_str = (
            " ".join([item for item in tags if isinstance(item, str)])
            if isinstance(tags, list)
            else ""
        )
        return f"{data.get('universal_id', '')} {data.get('name', '')} {data.get('description', '')} {tags_str}"

    def model_result(data: JSONDict) -> JSONDict:
        if not isinstance(data, dict):
            return {}

        is_virtual = data.get("type") == "virtual"
        universal_id = _string_field(data.get("universal_id"))
        if is_virtual and not universal_id:
            virtual_id_value = data.get("id")
            universal_id = _string_field(virtual_id_value)
        plugin_name = _string_field(data.get("plugin"), "virtual" if is_virtual else "unknown")
        state = _string_field(data.get("plugin_status"), "N/A") if not is_virtual else "N/A"
        return {
            "universal_id": universal_id,
            "display_name": _string_field(data.get("name"), universal_id),
            "plugin": plugin_name,
            "state": state,
        }

    return _filter_sequence(models, word_regexes, limit, model_text, model_result)


def _search_devices(
    hardware_snapshot: JSONDict | None,
    word_regexes: list[re.Pattern[str]],
    limit: int,
) -> list[JSONDict]:
    candidates = search_devices_candidates(hardware_snapshot)
    if not candidates:
        return []
    return _filter_sequence(
        candidates,
        word_regexes,
        limit,
        resolve_device_search_text,
        resolve_device_search_result,
    )


def perform_search(
    *,
    logger: TraceLogger,
    query: str,
    plugin_data: Iterable[JSONDict] | None,
    model_data: dict[str, list[JSONDict]] | None,
    hardware_data: JSONDict | None,
    limit: int,
) -> dict[str, list[JSONDict]]:
    empty_result = empty_search_result()
    if not query or (plugin_data is None and model_data is None and hardware_data is None):
        if plugin_data is None and model_data is None and hardware_data is None:
            logger.warning("Search called before datasets were set. Returning empty results.")
        return empty_result
    normalized_query = _normalize_search_string(query)
    if not normalized_query:
        return empty_result
    word_regexes = [re.compile(re.escape(word), re.IGNORECASE) for word in normalized_query.split()]
    return {
        "plugins": _search_plugins(plugin_data, word_regexes, limit),
        "models": _search_models(model_data, word_regexes, limit),
        "devices": _search_devices(hardware_data, word_regexes, limit),
    }


def prepare_search_inputs(
    *,
    plugin_data: Iterable[JSONDict] | None,
    model_data: dict[str, list[JSONDict]] | None,
    hardware_data: JSONDict | None,
) -> tuple[
    list[JSONDict] | None,
    dict[str, list[JSONDict]] | None,
    JSONDict | None,
]:
    processed_plugin_data = list(plugin_data) if plugin_data is not None else None
    return (
        processed_plugin_data,
        copy_json_dict_list_map(model_data) if model_data is not None else None,
        copy_json_dict(hardware_data) if hardware_data is not None else None,
    )
