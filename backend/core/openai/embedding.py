"""SoAI - Core embedding batching utilities [backend/core/openai/embedding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json import is_json_value
from core.validation.coercion import coerce_int_from_numberish
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "merge_embedding_batch_responses",
    "prepare_embedding_batches",
    "resolve_embedding_batch_limit",
)

MAX_EMBEDDING_USAGE_TOKEN_COUNT = 1_000_000_000


def _is_embedding_batch_input(embedding_input: JSONValue) -> bool:
    if not isinstance(embedding_input, list | tuple):
        return False
    if not embedding_input:
        return True
    if all(
        (not isinstance(input_item, bool)) and isinstance(input_item, int | float)
        for input_item in embedding_input
    ):
        return False
    return True


def resolve_embedding_batch_limit(
    plugin_config: JSONDict,
    model_parameters: JSONDict | None = None,
) -> int:
    candidate_values: list[JSONValue] = []
    if isinstance(model_parameters, dict):
        for key in (
            "embedding_batch_limit",
            "embedding_batch_size",
            "batch_size",
            "parallel",
            "ubatch_size",
        ):
            if key in model_parameters:
                candidate_values.append(model_parameters[key])
    if isinstance(plugin_config, dict):
        for key in (
            "embedding_batch_limit",
            "embedding_batch_size",
            "batch_size",
            "parallel",
            "ubatch_size",
        ):
            if key in plugin_config:
                candidate_values.append(plugin_config[key])
    for raw_value in candidate_values:
        if isinstance(raw_value, bool):
            continue
        if isinstance(raw_value, int | float | str):
            try:
                resolved_limit = int(raw_value)
            except (TypeError, ValueError):
                continue
            if resolved_limit >= 1:
                return resolved_limit
    return 1


def prepare_embedding_batches(
    embedding_input: JSONValue,
    max_batch_size: int,
) -> tuple[list[JSONDict], int]:
    if not _is_embedding_batch_input(embedding_input):
        return [{"offset": 0, "input": embedding_input, "size": 1}], 1
    if not isinstance(embedding_input, list | tuple):
        raise ValidationError("Embedding batch input must be a list or tuple.")
    input_items: list[JSONValue] = []
    for item in embedding_input:
        if not is_json_value(item):
            raise ValidationError("Embedding batch input contains a non-JSON value.")
        input_items.append(item)
    input_count = len(input_items)
    if isinstance(max_batch_size, bool):
        normalized_batch_size = 1
    else:
        try:
            normalized_batch_size = int(max_batch_size)
        except (TypeError, ValueError):
            normalized_batch_size = 1
    normalized_batch_size = max(normalized_batch_size, 1)
    batches: list[JSONDict] = []
    for start_index in range(0, input_count or 1, normalized_batch_size):
        batch_input = input_items[start_index : start_index + normalized_batch_size]
        batches.append({"offset": start_index, "input": batch_input, "size": len(batch_input)})
    return batches, input_count


def merge_embedding_batch_responses(
    batch_results: list[JSONDict],
    expected_items: int,
    default_model: str | None = None,
) -> JSONDict:
    combined_data: list[JSONDict] = []
    combined_prompt_tokens = 0
    combined_total_tokens = 0
    usage_present = False
    response_model: str | None = None
    response_object = "list"
    for batch_result in batch_results:
        batch_offset_value = batch_result.get("offset")
        if not is_strict_int(batch_offset_value):
            raise ValidationError("Embedding response offset must be an int.")
        batch_size_value = batch_result.get("size")
        if not is_strict_int(batch_size_value):
            raise ValidationError("Embedding response size must be an int.")
        batch_offset = batch_offset_value
        batch_size = batch_size_value
        response_payload = batch_result.get("response")
        if not isinstance(response_payload, dict):
            raise ValidationError("Embedding response payload must be a dict.")
        if response_model is None:
            model_value = response_payload.get("model")
            if isinstance(model_value, str):
                response_model = model_value
        object_value = response_payload.get("object")
        if isinstance(object_value, str) and object_value:
            response_object = object_value
        response_data = response_payload.get("data")
        if not isinstance(response_data, list):
            raise ValidationError("Embedding response is missing 'data' list.")
        if len(response_data) != batch_size:
            raise ValidationError("Embedding response size does not match request batch size.")
        seen_indices: list[int] = []
        for response_item in response_data:
            if not isinstance(response_item, dict):
                raise ValidationError("Embedding response item must be a dict.")
            response_item_index = response_item.get("index")
            if not is_strict_int(response_item_index):
                raise ValidationError("Embedding response item index must be an int.")
            if response_item_index < 0 or response_item_index >= batch_size:
                raise ValidationError("Embedding response item index is out of range.")
            if response_item_index in seen_indices:
                raise ValidationError("Embedding response contains duplicate indices.")
            seen_indices.append(response_item_index)
            combined_item = dict(response_item)
            combined_item["index"] = batch_offset + response_item_index
            combined_data.append(combined_item)
        usage_payload = response_payload.get("usage")
        if isinstance(usage_payload, dict):
            usage_present = True
            prompt_tokens = _coerce_optional_usage_token_count(usage_payload.get("prompt_tokens"))
            if prompt_tokens is not None:
                combined_prompt_tokens += prompt_tokens
            total_tokens = _coerce_optional_usage_token_count(usage_payload.get("total_tokens"))
            if total_tokens is not None:
                combined_total_tokens += total_tokens
    if expected_items and len(combined_data) != expected_items:
        raise ValidationError("Merged embeddings count does not match expected input count.")

    def _sort_key(data_item: JSONDict) -> int:
        index_value = data_item.get("index")
        return index_value if is_strict_int(index_value) else 0

    combined_data.sort(key=_sort_key)
    combined_data_json: list[JSONValue] = []
    for item in combined_data:
        combined_data_json.append(item)
    merged_payload: JSONDict = {
        "object": response_object,
        "data": combined_data_json,
    }
    if response_model or default_model:
        merged_payload["model"] = response_model or default_model
    if usage_present:
        merged_payload["usage"] = {
            "prompt_tokens": combined_prompt_tokens,
            "total_tokens": combined_total_tokens,
        }
    return merged_payload


def _coerce_optional_usage_token_count(value: JSONValue) -> int | None:
    parsed = coerce_int_from_numberish(value)
    if parsed is None:
        return None
    if parsed < 0 or parsed > MAX_EMBEDDING_USAGE_TOKEN_COUNT:
        return None
    return parsed
