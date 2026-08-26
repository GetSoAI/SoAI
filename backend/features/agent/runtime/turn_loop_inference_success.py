"""SoAI - Agent turn-loop successful inference helpers [backend/features/agent/runtime/turn_loop_inference_success.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.agent.runtime.openai_payload import replace_assistant_content_visible

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.types.json import JSONDict
    from features.api.runtime.preview_contract_output_validation import (
        PreviewContractOutputValidationResult,
    )

__all__ = ("resolve_preview_validated_assistant_text",)


async def resolve_preview_validated_assistant_text(
    *,
    final_payload: JSONDict,
    tool_calls: list[JSONDict],
    assistant_text: str | None,
    validate_visible_assistant_output: (
        Callable[[str], Awaitable[PreviewContractOutputValidationResult]] | None
    ),
) -> tuple[str | None, PreviewContractOutputValidationResult | None]:
    preview_contract_validation = None
    if (
        validate_visible_assistant_output is not None
        and not tool_calls
        and assistant_text is not None
    ):
        preview_contract_validation = await validate_visible_assistant_output(assistant_text)
        if preview_contract_validation.compliant:
            assistant_text = preview_contract_validation.resolved_text
            replace_assistant_content_visible(final_payload, assistant_text)
    return (assistant_text, preview_contract_validation)
