"""SoAI - Durable Chat input group execution [backend/features/chat/conversation_input_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.conversations.interaction_checkpoint import ConversationInputSuspended
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.types.json import JSONDict
from features.api.routes.webui.conversation_input_queue_events import (
    publish_current_input_queue_changed,
)
from features.chat.conversation_input_runtime import require_conversation_input_identity
from features.chat.conversation_input_variant_execution import (
    execute_conversation_input_variant,
)
from features.chat.conversation_input_variants import (
    apply_conversation_input_variant,
    resolve_conversation_input_variants,
)

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies
    from features.chat.conversation_input_variant_execution import (
        InputVariantTerminalState,
    )

__all__ = ("execute_claimed_conversation_input",)

LOGGER_NAME = "SoAI.features.chat.conversation_input_execution"
OPERATION = "chat.conversation_input.execute"


def resolve_recovered_variant_outcome(
    outcomes: list[JSONDict],
    request_id: str,
) -> tuple[InputVariantTerminalState, str] | None:
    matching = [outcome for outcome in outcomes if outcome.get("request_id") == request_id]
    if not matching:
        return None
    if len(matching) != 1 or matching[0].get("finalized_at_ms") is None:
        return ("effect_unknown", "interrupted_effect_unknown")
    finish_reason = matching[0].get("finish_reason")
    if finish_reason == "cancelled":
        return ("cancelled", "cancelled")
    if finish_reason == "error":
        return ("failed", "interrupted_after_finalization")
    return ("completed", "recovered_completed")


async def execute_claimed_conversation_input(
    api_dependencies: ApiDependencies,
    *,
    input_record: JSONDict,
    claim_owner: str,
    server_boot_id: str,
) -> None:
    input_id, conv_id, user_id, claim_generation = require_conversation_input_identity(
        input_record,
    )
    terminal_state: InputVariantTerminalState = "completed"
    terminal_code = "completed"
    suspended = False
    try:
        existing_outcomes = (
            await api_dependencies.database_input_execution.list_input_variant_outcomes(
                input_id=input_id,
            )
        )
        for variant in resolve_conversation_input_variants(input_record):
            existing = resolve_recovered_variant_outcome(
                existing_outcomes,
                variant.request_id,
            )
            if existing is not None:
                terminal_state, terminal_code = existing
                if terminal_state == "completed":
                    continue
                break
            terminal_state, terminal_code = await execute_conversation_input_variant(
                api_dependencies,
                input_record=apply_conversation_input_variant(input_record, variant),
                claim_owner=claim_owner,
                server_boot_id=server_boot_id,
            )
            if terminal_state != "completed":
                break
    except ConversationInputSuspended:
        suspended = True
    except asyncio.CancelledError:
        terminal_state = "cancelled"
        terminal_code = "cancelled"
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        terminal_state = "failed"
        terminal_code = str(coerced.code)
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Conversation input group execution failed.",
            operation=OPERATION,
            details={"input_id": input_id, "conv_id": conv_id},
        )
    finally:
        if not suspended:
            await uncancel_then_cleanup(
                api_dependencies.database_input_execution.terminalize_input(
                    input_id=input_id,
                    claim_generation=claim_generation,
                    claim_owner=claim_owner,
                    server_boot_id=server_boot_id,
                    terminal_state=terminal_state,
                    terminal_code=terminal_code,
                    terminal_args={},
                ),
            )
        await publish_current_input_queue_changed(
            api_dependencies=api_dependencies,
            user_id=user_id,
            conv_id=conv_id,
        )
