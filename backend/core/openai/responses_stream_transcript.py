"""SoAI - Durable result transcript for OpenAI Responses streams [backend/core/openai/responses_stream_transcript.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.openai.completion_token_progress import CompletionTokenSnapshotCursor
from core.openai.response_terminal_policy import (
    coerce_response_event_type,
    is_successful_response_status,
    is_terminal_response_payload,
    response_status_from_event,
    response_status_to_event_type,
)
from core.openai.responses_provider_events import (
    ResponsesProviderStreamError,
    decode_responses_provider_frame,
)
from core.openai.responses_provider_state import ResponsesProviderState
from core.types.json import JSONDict

__all__ = ("ResponsesStreamTranscript",)


class ResponsesStreamTranscript:
    def __init__(self, *, response_id: str, model: str, created_at: int) -> None:
        self._state = ResponsesProviderState(
            response_id=response_id,
            model=model,
            created_at=created_at,
        )
        self._terminal_observed = False
        self._terminal_status: str | None = None
        self._finalized = False
        self._token_cursor = CompletionTokenSnapshotCursor()

    def consume_frame(self, frame: str) -> None:
        if self._finalized:
            raise ResponsesProviderStreamError("Responses transcript is already finalized.")
        self._consume_frame(frame)

    def finalize(self) -> JSONDict:
        self._finalized = True
        return self.build_result_payload()

    @property
    def terminal_observed(self) -> bool:
        return self._terminal_observed

    def build_result_payload(self) -> JSONDict:
        if not self._terminal_observed:
            raise StateError("Responses stream ended without a terminal response event.")
        terminal_status = self._terminal_status
        if terminal_status is None or not is_successful_response_status(terminal_status):
            raise StateError("Responses provider did not complete successfully.")
        response = self._state.build_response_json(status=terminal_status)
        if response is None:
            raise StateError("Responses stream completed without a response payload.")
        return response

    def get_reported_usage(self) -> JSONDict | None:
        response = self.build_result_payload()
        usage = response.get("usage")
        return dict(usage) if isinstance(usage, dict) else None

    def get_visible_text(self) -> str:
        return "".join(self._iter_output_text(types={"output_text"}))

    def get_thinking_text(self) -> str:
        return "".join(self._iter_output_text(types={"reasoning_text", "summary_text"}))

    def get_tool_calls(self) -> list[JSONDict]:
        tool_calls: list[JSONDict] = []
        for item in self._output_items():
            if item.get("type") != "function_call":
                continue
            call_id = item.get("call_id")
            name = item.get("name")
            arguments = item.get("arguments")
            tool_calls.append(
                {
                    "id": call_id if isinstance(call_id, str) else "",
                    "type": "function",
                    "function": {
                        "name": name if isinstance(name, str) else "",
                        "arguments": arguments if isinstance(arguments, str) else "",
                    },
                }
            )
        return tool_calls

    def drain_completion_token_fragments(self) -> tuple[str, ...]:
        return self._token_cursor.take(
            visible_text=self.get_visible_text(),
            thinking_text=self.get_thinking_text(),
            tool_calls=self.get_tool_calls(),
        )

    def _consume_frame(self, frame: str) -> None:
        decoded = decode_responses_provider_frame(frame)
        for payload in decoded.payloads:
            if self._terminal_observed:
                raise ResponsesProviderStreamError(
                    "Responses provider emitted a payload after the terminal event."
                )
            if is_terminal_response_payload(payload):
                response = payload.get("response")
                if not isinstance(response, dict):
                    raise ResponsesProviderStreamError(
                        "Provider returned a malformed terminal Responses event."
                    )
                terminal_status = response_status_from_event(payload)
                event_type = coerce_response_event_type(payload.get("type"))
                if event_type != response_status_to_event_type(terminal_status):
                    raise ResponsesProviderStreamError(
                        "Provider returned an inconsistent terminal Responses event."
                    )
                if not is_successful_response_status(terminal_status):
                    raise ResponsesProviderStreamError(
                        "Responses provider did not complete successfully."
                    )
                self._terminal_observed = True
                self._terminal_status = terminal_status
            self._state.observe(payload)

    def _output_items(self) -> list[JSONDict]:
        response = self._state.build_response_json(status=self._terminal_status or "completed")
        output = response.get("output") if response is not None else None
        return (
            [dict(item) for item in output if isinstance(item, dict)]
            if isinstance(output, list)
            else []
        )

    def _iter_output_text(self, *, types: set[str]) -> list[str]:
        values: list[str] = []
        for item in self._output_items():
            for field in ("content", "summary"):
                parts = item.get(field)
                if not isinstance(parts, list):
                    continue
                for part in parts:
                    if not isinstance(part, dict) or part.get("type") not in types:
                        continue
                    text = part.get("text")
                    if isinstance(text, str):
                        values.append(text)
        return values
