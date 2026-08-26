"""SoAI - Database operation recovery status routes [backend/features/api/routes/system/system_database_operation_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends
from pydantic import BaseModel, Field

from core.database.operation_status import DatabaseOperationStatusValue
from core.state.access import AccessAction
from features.api.middleware.acl_enforcement import require_any_actions
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

__all__ = ("register_routes",)


class DatabaseOperationStatusResponse(BaseModel):
    operation_id: str = Field(min_length=1)
    status: DatabaseOperationStatusValue
    terminal: bool
    retry_safe: bool
    committed_at_ms: int | None
    expires_at_ms: int = Field(ge=0)


def register_routes(routers: ApiRouters) -> None:
    @routers.system.get(
        "/database/operations/{operation_id}",
        response_model=DatabaseOperationStatusResponse,
        dependencies=(
            Depends(
                require_any_actions(
                    AccessAction.SYSTEM_STATUS_READ,
                    AccessAction.OPENAI_API,
                )
            ),
        ),
    )
    async def get_database_operation_status(
        operation_id: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> DatabaseOperationStatusResponse:
        status = await api_context.dependencies.database_operation_status.resolve(operation_id)
        return DatabaseOperationStatusResponse(
            operation_id=status.operation_id,
            status=status.status,
            terminal=status.terminal,
            retry_safe=status.retry_safe,
            committed_at_ms=status.committed_at_ms,
            expires_at_ms=status.expires_at_ms,
        )
