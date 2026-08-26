"""SoAI - Password mutation transaction execution and successor collision recovery [backend/features/api/routes/webui/password_change_transaction_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace

from core.auth.jwt_claims import AccessTokenRecord
from core.auth.webui_sessions import WebuiSessionJtiCollisionError
from core.errors.exceptions import ApiError, ConflictError, SecurityError
from core.state.errors import DatabaseTimeoutError
from core.users.password_change import (
    PasswordChangeDatabaseResult,
    PasswordChangeTransaction,
)
from features.api.routes.webui.session_successor_credentials import (
    SessionSuccessorAllocator,
)
from features.api.routes.webui.user_mutation_responses import (
    raise_identity_mutation_failure,
)
from features.api.runtime.context import ApiContext


async def execute_password_change_transaction(
    *,
    api_context: ApiContext,
    transaction: PasswordChangeTransaction,
    successor_allocator: SessionSuccessorAllocator | None,
    actor_user_id: int,
    successor_username: str,
    successor_password_revision: int,
    operation_id: str,
) -> tuple[PasswordChangeDatabaseResult, AccessTokenRecord | None]:
    replacement_token = transaction.successor
    while True:
        try:
            result = await api_context.dependencies.database_user_mutations.change_password(
                transaction
            )
            return result, replacement_token
        except WebuiSessionJtiCollisionError as exception:
            if successor_allocator is None:
                raise SecurityError(
                    "A non-rotating password mutation collided with a session."
                ) from exception
            replacement_token = await successor_allocator.create(
                user_id=actor_user_id,
                username=successor_username,
                password_revision=successor_password_revision,
            )
            transaction = replace(transaction, successor=replacement_token)
        except ConflictError:
            raise_identity_mutation_failure("operation_id_conflict", operation_id)
        except DatabaseTimeoutError as exception:
            raise ApiError(
                "Identity mutation result is unknown.",
                code="identity_mutation_result_unknown",
                http_status=503,
                details={"operation_id": operation_id},
                cause=exception,
            ) from exception


__all__ = ("execute_password_change_transaction",)
