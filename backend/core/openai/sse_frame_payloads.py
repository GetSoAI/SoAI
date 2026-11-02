"""SoAI - OpenAI SSE frame payload parsing [backend/core/openai/sse_frame_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ModelOutputContractError
from core.openai.sse_block_decoder import decode_openai_sse_block

if TYPE_CHECKING:
    from core.openai.sse_block_decoder import DecodedSSEBlock
    from core.types.json import JSONDict

__all__ = (
    "parse_openai_sse_frame_payloads",
    "require_openai_sse_frame_payloads",
)

OPERATION_PARSE_OPENAI_SSE_FRAME_PAYLOADS = "sse_frame_payloads.parse_openai_sse_frame_payloads"


def parse_openai_sse_frame_payloads(frame: bytes | str) -> tuple[JSONDict, ...]:
    if isinstance(frame, bytes):
        try:
            frame_text = frame.decode("utf-8")
        except UnicodeDecodeError as exception:
            raise ModelOutputContractError(
                "OpenAI SSE frame contains invalid UTF-8.",
                details={"failure_type": "invalid_utf8"},
                cause=exception,
            ) from exception
    else:
        frame_text = frame
    decoded = decode_openai_sse_block(frame_text)
    return require_openai_sse_frame_payloads(decoded)


def require_openai_sse_frame_payloads(decoded: DecodedSSEBlock) -> tuple[JSONDict, ...]:
    if not decoded.is_terminated or not decoded.is_well_formed:
        raise ModelOutputContractError(
            "Provider returned a malformed OpenAI SSE frame.",
            operation=OPERATION_PARSE_OPENAI_SSE_FRAME_PAYLOADS,
            details={"failure_type": "malformed_frame"},
        )
    if len(decoded.data_events) > 1:
        raise ModelOutputContractError(
            "OpenAI SSE frame contains multiple data events.",
            operation=OPERATION_PARSE_OPENAI_SSE_FRAME_PAYLOADS,
            details={"failure_type": "multiple_data_events"},
        )
    return decoded.payloads
