"""SoAI - Messaging account deletion lifecycle [backend/features/messaging/account_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exception_logging import log_handled_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.messaging.account_validation import require_messaging_account_fence
from core.tasks.task_cancellation import cancel
from features.chat.conversation_input_cancellation import (
    cancel_active_conversation_input,
)
from features.messaging.account_callback_reconciliation import remove_messaging_account_callback

if TYPE_CHECKING:
    from core.messaging.account_models import MessagingConversationVersion
    from core.messaging.protocols import DatabaseMessagingAccountsProtocol
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("execute_messaging_account_delete",)

LOGGER_NAME = "SoAI.features.messaging.account_lifecycle"
OPERATION_DELETE = "messaging.account.delete"


async def execute_messaging_account_delete(
    *,
    database_accounts: DatabaseMessagingAccountsProtocol,
    api_dependencies: ApiDependencies,
    http_client: httpx2.AsyncClient,
    public_origin: str,
    user_id: int,
    account_id: str,
    expected_revision: int,
) -> tuple[MessagingConversationVersion, ...] | None:
    async with database_accounts.account_lifecycle_lock(account_id):
        fence = await database_accounts.begin_delete(user_id, account_id, expected_revision)
        if fence is None:
            return None
        account_fence = require_messaging_account_fence(fence.account)
        for active_input in fence.active_inputs:
            await cancel_active_conversation_input(
                api_dependencies,
                user_id=active_input.user_id,
                conv_id=active_input.conv_id,
                input_id=active_input.input_id,
                reason="Messaging account deleted.",
            )
        for task_id in fence.task_ids:
            try:
                await cancel(
                    api_dependencies.task_registry,
                    task_id,
                    reason="Messaging account deleted.",
                )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                log_handled_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="Messaging account task cancellation failed after durable fencing.",
                    operation=OPERATION_DELETE,
                    level="warning",
                    details={"account_id": account_id, "task_id": task_id},
                )
        account = await database_accounts.get_transport_account(
            account_id,
            account_fence.platform,
        )
        if account is not None:
            try:
                await remove_messaging_account_callback(
                    http_client,
                    account=account,
                    public_origin=public_origin,
                )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                log_handled_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="Messaging account provider cleanup failed after durable fencing.",
                    operation=OPERATION_DELETE,
                    level="warning",
                    details={"account_id": account_id},
                )
        return await database_accounts.finalize_delete(
            user_id,
            account_id,
            account_fence.lifecycle_generation,
        )
