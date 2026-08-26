"""SoAI - Prepared chat preview contract validation [backend/features/api/runtime/chat_execution/preview_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from features.api.runtime.chat_prompt_augmentation import (
    request_requires_preview_contract,
)
from features.api.runtime.preview_contract_output_validation import (
    PreviewContractOutputValidationResult,
    validate_preview_contract_output,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("build_preview_contract_validation_callback",)


def build_preview_contract_validation_callback(
    *,
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
    request_json: JSONDict,
) -> Callable[[str], Awaitable[PreviewContractOutputValidationResult]]:
    preview_contract_required = request_requires_preview_contract(request_json)

    async def validate_visible_assistant_output(
        assistant_text: str,
    ) -> PreviewContractOutputValidationResult:
        if not preview_contract_required:
            return PreviewContractOutputValidationResult(
                compliant=True,
                resolved_text=assistant_text,
                retry_detail=None,
                reason_code=None,
                repair_attempted=False,
                repair_succeeded=False,
            )
        return await validate_preview_contract_output(
            api_dependencies,
            conv_id=runtime.conv_id,
            user_id=int(runtime.user_id),
            assistant_text=assistant_text,
        )

    return validate_visible_assistant_output
