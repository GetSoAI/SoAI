"""SoAI - Shared cancellation token release workflow [backend/core/tasks/cancellation_token_release.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.cancellation_ids import is_system_cancellation_id

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.tasks.cancellation_types import RemoveTokenResult
    from core.tasks.protocols import (
        CancellationEventBusProtocol,
        CancellationHistoryProtocol,
        TokenCollectionProtocol,
    )

__all__ = ("release_cancellation_token",)


async def release_cancellation_token(
    *,
    token_collection: TokenCollectionProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    cancellation_id: str,
    token: CancellationTokenProtocol,
    publish_release_event: bool,
) -> RemoveTokenResult:
    remove_result = await token_collection.remove_token(cancellation_id, token)
    if remove_result.removed and publish_release_event:
        await cancellation_event_bus.publish_event("token_released", cancellation_id)
    if (
        remove_result.scope_cleared
        and publish_release_event
        and is_system_cancellation_id(cancellation_id)
    ):
        await cancellation_history.clear_scope(cancellation_id)
    return remove_result
