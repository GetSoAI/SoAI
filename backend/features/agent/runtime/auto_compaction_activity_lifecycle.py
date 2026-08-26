"""SoAI - Auto-compaction success and failure completion [backend/features/agent/runtime/auto_compaction_activity_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_STATUS_ERROR,
)
from features.agent.runtime.turn_compaction_activity_completion import (
    complete_auto_compaction_activity,
)
from features.agent.runtime.turn_compaction_activity_state import (
    resolve_terminal_error_message,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.agent.runtime.context_compaction.activity_result import (
        AutoCompactionActivityMetadata,
    )
    from features.agent.runtime.turn_compaction_activity_scope import (
        AutoCompactionActivityScope,
    )
    from features.agent.runtime.turn_compaction_activity_state import (
        AutoCompactionActivityState,
    )

__all__ = (
    "complete_auto_compaction_error_activity",
    "complete_auto_compaction_success_activity",
)


async def complete_auto_compaction_success_activity(
    *,
    activity: AutoCompactionActivityState,
    scope: AutoCompactionActivityScope,
    output_text: str,
    prompt_message: JSONDict | None,
    metadata: AutoCompactionActivityMetadata,
) -> None:
    await complete_auto_compaction_activity(
        activity=activity,
        scope=scope,
        status=TOOL_CALL_STATUS_COMPLETED,
        output_text=output_text,
        prompt_message=prompt_message,
        error_message=None,
        metadata=metadata,
    )


async def complete_auto_compaction_error_activity(
    *,
    activity: AutoCompactionActivityState,
    scope: AutoCompactionActivityScope,
    exception: BaseException,
    cancelled: bool,
) -> None:
    output_text = "Context compaction cancelled." if cancelled else "Context compaction failed."
    status = TOOL_CALL_STATUS_CANCELLED if cancelled else TOOL_CALL_STATUS_ERROR
    await uncancel_then_cleanup(
        complete_auto_compaction_activity(
            activity=activity,
            scope=scope,
            status=status,
            output_text=output_text,
            prompt_message=None,
            error_message=resolve_terminal_error_message(
                exception,
                default_message=output_text,
            ),
            metadata=None,
        ),
    )
