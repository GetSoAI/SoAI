"""SoAI - Prepared chat lifecycle helpers [backend/features/api/runtime/chat_execution/lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json_value import copy_json_dict
from features.api.runtime.task_metadata import build_inference_task_metadata

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.chat_execution.contracts import PreparedChatExecution

__all__ = ("build_prepared_chat_task_metadata", "build_prepared_inference_payload")


def build_prepared_chat_task_metadata(
    request: RequestProtocol,
    prepared_execution: PreparedChatExecution,
) -> JSONDict:
    task_metadata = build_inference_task_metadata(
        prepared_execution.request_context,
        request,
        prepared_execution.effective_model_id,
        prepared_execution.request_event_class.__name__,
    )
    if prepared_execution.prompt_tokens is not None:
        task_metadata["prompt_tokens"] = prepared_execution.prompt_tokens
    return task_metadata


def build_prepared_inference_payload(prepared_execution: PreparedChatExecution) -> JSONDict:
    prepared_agent_request = prepared_execution.prepared_agent_request
    if prepared_agent_request is not None:
        return copy_json_dict(prepared_agent_request.final_payload)
    return dict(prepared_execution.inference_payload)
