"""SoAI - OpenAI Responses provider stream state accumulation [backend/core/openai/responses_provider_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.openai.responses_events import (
    build_canonical_response_json,
    build_response_event_from_json,
)
from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_json_dict
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

__all__ = ("ResponsesProviderState",)


def _coerce_output_index(value: JSONValue, default: int) -> int:
    resolved = coerce_optional_non_negative_int_strict(value)
    return resolved if resolved is not None else default


def _coerce_content_index(value: JSONValue) -> int:
    resolved = coerce_optional_non_negative_int_strict(value)
    return resolved if resolved is not None else 0


@dataclass(slots=True)
class ResponsesProviderState:
    response_id: str
    model: str
    created_at: int
    _response: JSONDict | None = None
    _output_items: dict[int, JSONDict] = field(default_factory=dict[int, JSONDict])
    _item_indexes: dict[str, int] = field(default_factory=dict[str, int])

    def has_state(self) -> bool:
        return self._response is not None or bool(self._output_items)

    def observe(self, payload: JSONDict) -> None:
        event_type_value = payload.get("type")
        event_type = event_type_value if isinstance(event_type_value, str) else ""
        response_value = payload.get("response")
        response = coerce_json_dict(response_value)
        if response is not None:
            existing = dict(self._response) if isinstance(self._response, dict) else {}
            merged = {**existing, **response}
            output_value = merged.get("output")
            if isinstance(output_value, list):
                for index, item_value in enumerate(output_value):
                    item = coerce_json_dict(item_value)
                    if item is None:
                        continue
                    self._set_output_item(index, item)
            self._response = merged
        if event_type == "response.output_item.added":
            self._observe_output_item_event(payload)
            return
        if event_type == "response.output_item.done":
            self._observe_output_item_event(payload)
            return
        if event_type == "response.output_text.delta":
            self._observe_output_text_delta(payload)
            return
        if event_type == "response.function_call_arguments.delta":
            self._observe_function_call_delta(payload)
            return
        if event_type == "response.reasoning_summary_text.delta":
            self._observe_reasoning_summary_delta(payload)
            return
        if event_type == "response.reasoning_text.delta":
            self._observe_reasoning_text_delta(payload)

    def normalize_event_indexes(self, payload: JSONDict) -> JSONDict:
        normalized = dict(payload)
        event_type_value = normalized.get("type")
        event_type = event_type_value if isinstance(event_type_value, str) else ""
        item = coerce_json_dict(normalized.get("item"))
        if item is not None:
            item_id_value = item.get("id")
            item_id = item_id_value if isinstance(item_id_value, str) else ""
            known_index = self._item_indexes.get(item_id) if item_id else None
            default_index = len(self._output_items)
            if event_type == "response.output_item.done":
                default_index = known_index if known_index is not None else default_index
            normalized["output_index"] = _coerce_output_index(
                normalized.get("output_index"),
                default_index,
            )
            return normalized
        item_id_value = normalized.get("item_id")
        item_id = item_id_value if isinstance(item_id_value, str) else ""
        if item_id:
            normalized["output_index"] = self._resolve_item_index(normalized)
        if event_type in {
            "response.content_part.added",
            "response.content_part.done",
            "response.output_text.delta",
            "response.output_text.done",
            "response.refusal.delta",
            "response.refusal.done",
            "response.reasoning_text.delta",
            "response.reasoning_text.done",
        }:
            normalized["content_index"] = _coerce_content_index(normalized.get("content_index"))
        if event_type in {
            "response.reasoning_summary_part.added",
            "response.reasoning_summary_part.done",
            "response.reasoning_summary_text.delta",
            "response.reasoning_summary_text.done",
        }:
            normalized["summary_index"] = _coerce_content_index(normalized.get("summary_index"))
        return normalized

    def build_response_event(self, *, status: str) -> JSONDict | None:
        if not self.has_state():
            return None
        response = dict(self._response) if self._response is not None else {}
        response["output"] = self._build_output_list(response.get("output"))
        response = build_canonical_response_json(
            response_json=response,
            response_id=self.response_id,
            status=status,
            model=self.model,
            created_at=self.created_at,
        )
        return build_response_event_from_json(response_json=response, default_status=status)

    def build_response_json(self, *, status: str) -> JSONDict | None:
        response_event = self.build_response_event(status=status)
        if response_event is None:
            return None
        response_value = response_event.get("response")
        return coerce_json_dict(response_value)

    def _observe_output_item_event(self, payload: JSONDict) -> None:
        item = coerce_json_dict(payload.get("item"))
        if item is None:
            return
        output_index = _coerce_output_index(payload.get("output_index"), len(self._output_items))
        self._set_output_item(output_index, item)

    def _observe_output_text_delta(self, payload: JSONDict) -> None:
        output_index = _coerce_output_index(payload.get("output_index"), 0)
        item = self._get_or_create_message_item(output_index, payload)
        content_index = _coerce_content_index(payload.get("content_index"))
        delta_value = payload.get("delta")
        delta = delta_value if isinstance(delta_value, str) else ""
        content_value = item.get("content")
        content = list(content_value) if isinstance(content_value, list) else []
        while len(content) <= content_index:
            content.append({"type": "output_text", "text": "", "annotations": []})
        part_value = content[content_index]
        part: JSONDict = (
            dict(part_value)
            if isinstance(part_value, dict)
            else {"type": "output_text", "text": "", "annotations": []}
        )
        part_type_value = part.get("type")
        part["type"] = (
            part_type_value
            if isinstance(part_type_value, str) and part_type_value
            else "output_text"
        )
        existing_text_value = part.get("text")
        existing_text = existing_text_value if isinstance(existing_text_value, str) else ""
        part["text"] = f"{existing_text}{delta}"
        annotations_value = part.get("annotations")
        if not isinstance(annotations_value, list):
            part["annotations"] = []
        content[content_index] = part
        item["content"] = content
        self._set_output_item(output_index, item)

    def _observe_function_call_delta(self, payload: JSONDict) -> None:
        output_index = self._resolve_item_index(payload)
        item = self._get_or_create_function_call_item(output_index, payload)
        delta_value = payload.get("delta")
        delta = delta_value if isinstance(delta_value, str) else ""
        arguments_value = item.get("arguments")
        arguments = arguments_value if isinstance(arguments_value, str) else ""
        item["arguments"] = f"{arguments}{delta}"
        self._set_output_item(output_index, item)

    def _observe_reasoning_summary_delta(self, payload: JSONDict) -> None:
        output_index = self._resolve_item_index(payload)
        item = self._get_or_create_reasoning_item(output_index)
        summary_value = item.get("summary")
        summary = list(summary_value) if isinstance(summary_value, list) else []
        summary_index = _coerce_content_index(payload.get("summary_index"))
        while len(summary) <= summary_index:
            summary.append({"type": "summary_text", "text": ""})
        summary_part_value = summary[summary_index]
        summary_part = (
            dict(summary_part_value)
            if isinstance(summary_part_value, dict)
            else {"type": "summary_text", "text": ""}
        )
        delta_value = payload.get("delta")
        delta = delta_value if isinstance(delta_value, str) else ""
        text_value = summary_part.get("text")
        summary_part["text"] = f"{text_value if isinstance(text_value, str) else ''}{delta}"
        summary[summary_index] = summary_part
        item["summary"] = summary
        self._set_output_item(output_index, item)

    def _observe_reasoning_text_delta(self, payload: JSONDict) -> None:
        output_index = self._resolve_item_index(payload)
        item = self._get_or_create_reasoning_item(output_index)
        content_value = item.get("content")
        content = list(content_value) if isinstance(content_value, list) else []
        content_index = _coerce_content_index(payload.get("content_index"))
        while len(content) <= content_index:
            content.append({"type": "reasoning_text", "text": ""})
        content_part_value = content[content_index]
        content_part = (
            dict(content_part_value)
            if isinstance(content_part_value, dict)
            else {"type": "reasoning_text", "text": ""}
        )
        delta_value = payload.get("delta")
        delta = delta_value if isinstance(delta_value, str) else ""
        text_value = content_part.get("text")
        content_part["text"] = f"{text_value if isinstance(text_value, str) else ''}{delta}"
        content[content_index] = content_part
        item["content"] = content
        self._set_output_item(output_index, item)

    def _resolve_item_index(self, payload: JSONDict) -> int:
        item_id_value = payload.get("item_id")
        item_id = item_id_value if isinstance(item_id_value, str) and item_id_value else ""
        if item_id and item_id in self._item_indexes:
            return self._item_indexes[item_id]
        return _coerce_output_index(payload.get("output_index"), 0)

    def _set_output_item(self, output_index: int, item: JSONDict) -> None:
        normalized = dict(item)
        self._output_items[output_index] = normalized
        item_id_value = normalized.get("id")
        if isinstance(item_id_value, str) and item_id_value:
            self._item_indexes[item_id_value] = output_index

    def _build_output_list(self, existing_output_value: JSONValue) -> list[JSONDict]:
        existing_output: list[JSONDict] = []
        if isinstance(existing_output_value, list):
            for item_value in existing_output_value:
                item = coerce_json_dict(item_value)
                if item is not None:
                    existing_output.append(dict(item))
        if not self._output_items:
            return existing_output
        merged = list(existing_output)
        for output_index in sorted(self._output_items):
            while len(merged) <= output_index:
                merged.append({})
            merged[output_index] = dict(self._output_items[output_index])
        return [item for item in merged if item]

    def _get_or_create_message_item(self, output_index: int, payload: JSONDict) -> JSONDict:
        existing = self._output_items.get(output_index)
        if isinstance(existing, dict):
            return dict(existing)
        item_id_value = payload.get("item_id")
        item_id = item_id_value if isinstance(item_id_value, str) and item_id_value else ""
        return {
            "id": item_id or f"msg_{output_index}",
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [],
        }

    def _get_or_create_function_call_item(self, output_index: int, payload: JSONDict) -> JSONDict:
        existing = self._output_items.get(output_index)
        if isinstance(existing, dict):
            return dict(existing)
        item_id_value = payload.get("item_id")
        item_id = item_id_value if isinstance(item_id_value, str) and item_id_value else ""
        return {
            "id": item_id or f"fc_{output_index}",
            "type": "function_call",
            "call_id": item_id or f"call_{output_index}",
            "name": "",
            "arguments": "",
        }

    def _get_or_create_reasoning_item(self, output_index: int) -> JSONDict:
        existing = self._output_items.get(output_index)
        if isinstance(existing, dict):
            return dict(existing)
        return {"id": f"rs_{output_index}", "type": "reasoning", "summary": []}
