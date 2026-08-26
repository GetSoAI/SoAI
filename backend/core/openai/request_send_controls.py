"""SoAI - OpenAI request parameter send controls [backend/core/openai/request_send_controls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.output_token_cap import OUTPUT_TOKEN_CAP_FIELDS

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("apply_request_send_controls",)

_SEND_CONTROL_GROUPS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("reasoning_effort",), "reasoning_effort_send_enabled"),
    (OUTPUT_TOKEN_CAP_FIELDS, "max_completion_tokens_send_enabled"),
    (("top_p",), "top_p_send_enabled"),
    (("frequency_penalty",), "frequency_penalty_send_enabled"),
    (("presence_penalty",), "presence_penalty_send_enabled"),
    (("stop",), "stop_send_enabled"),
)


def _drop_send_control_flags(payload: JSONDict) -> None:
    for key in tuple(payload):
        if key.endswith("_send_enabled"):
            payload.pop(key, None)


def apply_request_send_controls(payload: JSONDict) -> None:
    logprobs_send_enabled = payload.get("logprobs_send_enabled")
    for parameters, flag in _SEND_CONTROL_GROUPS:
        if payload.get(flag) is False:
            for parameter in parameters:
                payload.pop(parameter, None)
    if logprobs_send_enabled is False or payload.get("logprobs") is False:
        payload.pop("logprobs", None)
        payload.pop("top_logprobs", None)
    elif logprobs_send_enabled is True:
        payload["logprobs"] = True
        if payload.get("top_logprobs") is None:
            payload.pop("top_logprobs", None)
    _drop_send_control_flags(payload)
