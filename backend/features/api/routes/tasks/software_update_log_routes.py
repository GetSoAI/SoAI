"""SoAI - Software update task log routes [backend/features/api/routes/tasks/software_update_log_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from typing import Literal

from fastapi import Depends, Request
from pydantic import BaseModel, Field

from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.state.access import AccessAction
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.status_transitions import update_status
from core.tasks.type_catalog import TASK_TYPE_SOFTWARE_UPDATE
from features.api.routes.tasks.task_query_models import SoftwareUpdateLogRequest
from features.api.runtime.access_dependencies import restart_protected_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_bad_request

__all__ = (
    "SoftwareUpdateLogResponse",
    "register_routes",
)


class SoftwareUpdateLogResponse(BaseModel):
    success: bool
    task_id: str = Field(min_length=1)
    status: Literal["started", "completed", "failed"] | None = None
    message: str | None = None


def register_routes(routers: ApiRouters) -> None:
    @routers.tasks.post(
        "/software-update/log",
        status_code=201,
        response_model=SoftwareUpdateLogResponse,
        dependencies=restart_protected_dependencies(AccessAction.SOFTWARE_UPDATE),
    )
    async def log_software_update(
        request: Request,
        payload: SoftwareUpdateLogRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> SoftwareUpdateLogResponse:
        registry = api_context.dependencies.task_registry
        task_seed = f"software_update:{payload.from_version}:{payload.to_version}".encode()
        task_id = f"task_{hashlib.sha256(task_seed).hexdigest()[:32]}"
        existing_task = await registry.get(task_id)
        if payload.status == "started":
            if existing_task and (not existing_task.status.is_terminal()):
                return SoftwareUpdateLogResponse(
                    success=True,
                    task_id=task_id,
                    message="Update task already in progress",
                )
            await create(
                registry,
                task_id=task_id,
                task_type=TASK_TYPE_SOFTWARE_UPDATE,
                owner_id="updater",
                owner_type="system",
                user_id=0,
                cancellation_id=build_soai_id(
                    ("sys", "software_update", safe_or_hashed_segment(task_id)),
                ),
                metadata={
                    "from_version": payload.from_version,
                    "to_version": payload.to_version,
                },
            )
            await update_status(
                registry,
                task_id,
                TaskStatus.WORKING,
                status_message=payload.message or "Software update started",
            )
            log_audit_event(
                request,
                "SOFTWARE_UPDATE_STARTED",
                task_id,
                {"from": payload.from_version, "to": payload.to_version},
            )
            api_context.dependencies.metrics_manager.increment_counter(
                "api",
                "tasks",
                "software_update_started",
            )
            return SoftwareUpdateLogResponse(success=True, task_id=task_id, status="started")
        if payload.status == "completed":
            if not existing_task:
                await create(
                    registry,
                    task_id=task_id,
                    task_type=TASK_TYPE_SOFTWARE_UPDATE,
                    owner_id="updater",
                    owner_type="system",
                    user_id=0,
                    cancellation_id=build_soai_id(
                        ("sys", "software_update", safe_or_hashed_segment(task_id)),
                    ),
                    metadata={
                        "from_version": payload.from_version,
                        "to_version": payload.to_version,
                        "auto_created": True,
                    },
                )
            await finalize(
                registry,
                task_id,
                TaskStatus.COMPLETED,
                result={
                    "from_version": payload.from_version,
                    "to_version": payload.to_version,
                    "message": payload.message,
                },
            )
            log_audit_event(
                request,
                "SOFTWARE_UPDATE_COMPLETED",
                task_id,
                {"from": payload.from_version, "to": payload.to_version},
            )
            api_context.dependencies.metrics_manager.increment_counter(
                "api",
                "tasks",
                "software_update_completed",
            )
            return SoftwareUpdateLogResponse(success=True, task_id=task_id, status="completed")
        if payload.status == "failed":
            if not existing_task:
                await create(
                    registry,
                    task_id=task_id,
                    task_type=TASK_TYPE_SOFTWARE_UPDATE,
                    owner_id="updater",
                    owner_type="system",
                    user_id=0,
                    cancellation_id=build_soai_id(
                        ("sys", "software_update", safe_or_hashed_segment(task_id)),
                    ),
                    metadata={
                        "from_version": payload.from_version,
                        "to_version": payload.to_version,
                        "auto_created": True,
                    },
                )
            await finalize(
                registry,
                task_id,
                TaskStatus.FAILED,
                error_code=500,
                error_message=payload.message or "Software update failed",
            )
            log_audit_event(
                request,
                "SOFTWARE_UPDATE_FAILED",
                task_id,
                {
                    "from": payload.from_version,
                    "to": payload.to_version,
                    "error": payload.message,
                },
            )
            api_context.dependencies.metrics_manager.increment_counter(
                "api",
                "tasks",
                "software_update_failed",
            )
            return SoftwareUpdateLogResponse(success=True, task_id=task_id, status="failed")
        raise_bad_request(
            request,
            f"Invalid status: {payload.status}. Must be 'started', 'completed', or 'failed'.",
            error_type="invalid_status",
        )
