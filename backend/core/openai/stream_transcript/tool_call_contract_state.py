"""SoAI - OpenAI stream tool-call contract state [backend/core/openai/stream_transcript/tool_call_contract_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("OpenAIStreamToolCallContractState",)


class OpenAIStreamToolCallContractState:
    def __init__(self) -> None:
        self._highest_started_stream_index: int | None = None
        self._violation_summary: JSONDict | None = None

    def observe(
        self,
        *,
        call_index: int | None,
        call_id: str | None,
        existing_arguments: str | None,
        arguments_fragment: str | None,
        call_started: bool,
    ) -> None:
        existing_arguments_text = existing_arguments if existing_arguments else None
        arguments_fragment_text = arguments_fragment if arguments_fragment else None
        has_out_of_order_arguments = (
            call_index is not None
            and self._highest_started_stream_index is not None
            and self._highest_started_stream_index > call_index
        )
        if (
            existing_arguments_text is not None
            and arguments_fragment_text is not None
            and has_out_of_order_arguments
            and self._violation_summary is None
        ):
            self._violation_summary = {
                "type": "out_of_order_tool_call_arguments",
                "resumed_stream_index": call_index,
                "highest_started_stream_index": self._highest_started_stream_index,
                "call_id": call_id,
                "existing_arguments_length": len(existing_arguments_text),
                "appended_arguments_length": len(arguments_fragment_text),
            }
        if (
            call_started
            and call_index is not None
            and (
                self._highest_started_stream_index is None
                or call_index > self._highest_started_stream_index
            )
        ):
            self._highest_started_stream_index = call_index

    def get_violation_summary(self) -> JSONDict | None:
        if self._violation_summary is None:
            return None
        return dict(self._violation_summary)
