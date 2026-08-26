"""SoAI - Incremental completion token progress [backend/core/openai/completion_token_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.types.json import JSONDict, JSONValue

__all__ = ("CompletionTokenSnapshotCursor",)


@dataclass(slots=True)
class CompletionTokenSnapshotCursor:
    visible_text: str = ""
    thinking_text: str = ""
    tool_fields: dict[str, str] = field(default_factory=dict[str, str])

    def take(
        self,
        *,
        visible_text: str,
        thinking_text: str,
        tool_calls: list[JSONDict],
    ) -> tuple[str, ...]:
        fragments: list[str] = []
        visible_fragment = self._resolve_fragment(self.visible_text, visible_text)
        if visible_fragment:
            fragments.append(visible_fragment)
        self.visible_text = visible_text
        thinking_fragment = self._resolve_fragment(self.thinking_text, thinking_text)
        if thinking_fragment:
            fragments.append(thinking_fragment)
        self.thinking_text = thinking_text
        current_tool_fields = self._flatten_tool_fields(tool_calls)
        for field_key, current_value in current_tool_fields.items():
            previous_value = self.tool_fields.get(field_key, "")
            fragment = self._resolve_fragment(previous_value, current_value)
            if fragment:
                fragments.append(fragment)
        self.tool_fields = current_tool_fields
        return tuple(fragments)

    def _resolve_fragment(self, previous_value: str, current_value: str) -> str:
        if current_value.startswith(previous_value):
            return current_value[len(previous_value) :]
        shared_prefix_length = 0
        for previous_character, current_character in zip(
            previous_value,
            current_value,
            strict=False,
        ):
            if previous_character != current_character:
                break
            shared_prefix_length += 1
        return current_value[shared_prefix_length:]

    def _flatten_tool_fields(self, tool_calls: list[JSONDict]) -> dict[str, str]:
        fields: dict[str, str] = {}
        for index, tool_call in enumerate(tool_calls):
            self._set_field(fields, f"{index}:id", tool_call.get("id"))
            self._set_field(fields, f"{index}:type", tool_call.get("type"))
            function_value = tool_call.get("function")
            if not isinstance(function_value, dict):
                continue
            self._set_field(fields, f"{index}:name", function_value.get("name"))
            self._set_field(fields, f"{index}:arguments", function_value.get("arguments"))
        return fields

    def _set_field(self, fields: dict[str, str], key: str, value: JSONValue | None) -> None:
        if isinstance(value, str) and value:
            fields[key] = value
