"""SoAI - Durable input cancellation admission [backend/features/chat/conversation_input_cancellation_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.types.json import JSONDict
from core.validation.record_fields import require_int, require_non_empty_str
from features.api.routes.webui.conversation_input_queue_events import (
    publish_current_input_queue_changed,
)
from features.api.runtime.container.types import ApiDependencies

__all__ = ("terminalize_claimed_input_if_cancelled",)


def _resolve_claimed_input_request_id(claimed: JSONDict, input_id: str) -> str:
    request_id = claimed.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        return request_id.strip()
    if claimed.get("state") == "materializing":
        return f"chat_{input_id}"
    raise StateError("Conversation input request id is invalid.")


async def terminalize_claimed_input_if_cancelled(
    api_dependencies: ApiDependencies,
    *,
    claimed: JSONDict,
    input_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
) -> bool:
    conv_id = require_non_empty_str(
        claimed.get("conv_id"),
        label="Conversation input conversation",
        build_error=StateError,
    )
    user_id = require_int(
        claimed.get("user_id"),
        label="Conversation input owner",
        build_error=StateError,
        minimum=1,
    )
    request_id = _resolve_claimed_input_request_id(claimed, input_id)
    accepted = await api_dependencies.database_stream_cancellations.is_accepted_for_input(
        conv_id=conv_id,
        user_id=user_id,
        request_id=request_id,
    )
    if not accepted:
        return False
    await api_dependencies.database_input_execution.terminalize_input(
        input_id=input_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
        terminal_state="cancelled",
        terminal_code="cancelled",
        terminal_args={},
    )
    await publish_current_input_queue_changed(
        api_dependencies=api_dependencies,
        user_id=user_id,
        conv_id=conv_id,
    )
    return True
