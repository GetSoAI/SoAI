"""SoAI - Cancellation token context manager [backend/core/tasks/cancellation_token_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from core.concurrency.cancellation import CancellationToken
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.tasks.cancellation_ids import (
    normalize_cancellation_id,
)
from core.tasks.cancellation_token_release import release_cancellation_token
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TokenCollectionProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("cancellation_token_scope",)

LOGGER_NAME = "SoAI.core.tasks.cancellation_token_scope"
OPERATION = "task_helper.cancellation_token_scope"


@asynccontextmanager
async def cancellation_token_scope(
    token_collection: TokenCollectionProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    *,
    cancellation_id: str,
    owner: str,
    metadata: dict[str, JSONValue] | None = None,
    on_cancel: Callable[[str], None] | None = None,
    logger: LoggerProtocol | None = None,
) -> AsyncGenerator[CancellationTokenProtocol]:
    normalized_id = normalize_cancellation_id(cancellation_id)
    token = CancellationToken(
        normalized_id,
        owner=owner,
        metadata=metadata,
        on_cancel=on_cancel,
    )
    token_added = False
    registration_event_published = False
    try:
        add_result = await token_collection.add_token(normalized_id, token)
        token_added = add_result.added
        if add_result.added:
            await cancellation_event_bus.publish_event("token_registered", normalized_id)
            registration_event_published = True
        existing_reason = await cancellation_history.get_reason(normalized_id)
        if existing_reason:
            token.cancel(existing_reason)
    except asyncio.CancelledError as exception:
        if token_added:
            await _cleanup_token_scope_setup_failure(
                token_collection=token_collection,
                cancellation_history=cancellation_history,
                cancellation_event_bus=cancellation_event_bus,
                cancellation_id=normalized_id,
                token=token,
                publish_release_event=registration_event_published,
                primary_exception=exception,
            )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        if token_added:
            await _cleanup_token_scope_setup_failure(
                token_collection=token_collection,
                cancellation_history=cancellation_history,
                cancellation_event_bus=cancellation_event_bus,
                cancellation_id=normalized_id,
                token=token,
                publish_release_event=registration_event_published,
                primary_exception=exception,
            )
        raise
    try:
        yield token
    finally:
        try:
            await uncancel_then_cleanup(
                release_cancellation_token(
                    token_collection=token_collection,
                    cancellation_history=cancellation_history,
                    cancellation_event_bus=cancellation_event_bus,
                    cancellation_id=normalized_id,
                    token=token,
                    publish_release_event=True,
                ),
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger or get_logger(LOGGER_NAME),
                exception,
                message="Failed to release cancellation token (non-critical).",
                operation=OPERATION,
                details={"cancellation_id": cancellation_id, "owner": owner},
                level="debug",
            )


async def _cleanup_token_scope_setup_failure(
    *,
    token_collection: TokenCollectionProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    cancellation_id: str,
    token: CancellationTokenProtocol,
    publish_release_event: bool,
    primary_exception: BaseException,
) -> None:
    try:
        await uncancel_then_cleanup(
            release_cancellation_token(
                token_collection=token_collection,
                cancellation_history=cancellation_history,
                cancellation_event_bus=cancellation_event_bus,
                cancellation_id=cancellation_id,
                token=token,
                publish_release_event=publish_release_event,
            ),
        )
    except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
        primary_exception.add_note(
            f"Cancellation token setup cleanup failed: {cleanup_exception}",
        )
