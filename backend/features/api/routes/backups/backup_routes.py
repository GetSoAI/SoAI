"""SoAI - REST API routes for backup lifecycle operations [backend/features/api/routes/backups/backup_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import FileResponse, JSONResponse

from core.audit.constants import (
    AUDIT_BACKUP_CREATE,
    AUDIT_BACKUP_DELETE,
    AUDIT_BACKUP_EXPORT,
    AUDIT_BACKUP_LIST,
    AUDIT_BACKUP_RESTORE,
    AUDIT_BACKUP_VERIFY,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    ConflictError,
    InsufficientDiskSpaceError,
    NotFoundError,
    StateError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.routes.backups.task_starter import start_backup_task
from features.api.routes.backups.validation import resolve_validated_backup_id
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    get_request_trace_id,
    resolve_api_context,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import (
    raise_conflict,
    raise_invalid_request,
    raise_not_found,
    raise_server_error,
)
from features.api.runtime.responses import create_task_accepted_response
from features.api.runtime.task_api_errors import raise_disk_space_api_error

__all__ = (
    "create_backup",
    "delete_backup",
    "export_backup",
    "list_backups",
    "register_endpoints",
    "register_routes",
    "restore_backup",
    "verify_backup",
)

LOGGER_NAME = "SoAI.features.api.backup_routes"
OPERATION_API_BACKUP_CREATE_BACKUP = "api_backup.create_backup"
OPERATION_API_BACKUP_DELETE_BACKUP = "api_backup.delete_backup"
OPERATION_API_BACKUP_EXPORT_BACKUP = "api_backup.export_backup"
OPERATION_API_BACKUP_LIST_BACKUPS = "api_backup.list_backups"


async def list_backups(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    log_audit_event(request, AUDIT_BACKUP_LIST, "backup_manager")
    backup_service = api_context.dependencies.backup_service
    if backup_service is None:
        raise_server_error(request, "Backup service is unavailable.")
    try:
        backups = await backup_service.list_backups()
        return JSONResponse(content={"backups": backups})
    except StateError as exception:
        raise_server_error(request, exception.message)
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation="api_backup.list_backups")
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to list backups",
            operation=OPERATION_API_BACKUP_LIST_BACKUPS,
        )
        raise_server_error(request, "Failed to list backups due to an internal error.")


async def create_backup(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    log_audit_event(request, AUDIT_BACKUP_CREATE, "backup_manager")
    backup_service = api_context.dependencies.backup_service
    if backup_service is None:
        raise_server_error(request, "Backup service is unavailable.")
    if not backup_service.is_operational():
        raise_server_error(request, "Backup service is not operational.")
    try:
        task_id = await backup_service.start_create_backup_task(user_id=current_user["id"])
        return create_task_accepted_response(task_id=task_id, commit_deadline_ts_ms=None)
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation="api_backup.create_backup")
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Backup creation failed",
            operation=OPERATION_API_BACKUP_CREATE_BACKUP,
        )
        raise_server_error(request, "Backup creation failed due to an internal error.")


async def restore_backup(
    request: Request,
    backup_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    validated_backup_id = resolve_validated_backup_id(request, backup_id)
    log_audit_event(
        request,
        AUDIT_BACKUP_RESTORE,
        "backup_manager",
        details={"backup_id": validated_backup_id},
    )
    backup_service = api_context.dependencies.backup_service
    if backup_service is None:
        raise_server_error(request, "Backup service is unavailable.")
    return await start_backup_task(
        request,
        validated_backup_id=validated_backup_id,
        user_id=current_user["id"],
        start_task=backup_service.start_restore_backup_task,
        operation="api_backup.restore_backup",
        failure_log_message="Backup restoration failed",
        failure_user_message="Backup restoration failed due to an internal error.",
    )


async def verify_backup(
    request: Request,
    backup_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    validated_backup_id = resolve_validated_backup_id(request, backup_id)
    log_audit_event(
        request,
        AUDIT_BACKUP_VERIFY,
        "backup_manager",
        details={"backup_id": validated_backup_id},
    )
    backup_service = api_context.dependencies.backup_service
    if backup_service is None:
        raise_server_error(request, "Backup service is unavailable.")
    return await start_backup_task(
        request,
        validated_backup_id=validated_backup_id,
        user_id=current_user["id"],
        start_task=backup_service.start_verify_backup_task,
        operation="api_backup.verify_backup",
        failure_log_message="Backup verification failed",
        failure_user_message="Backup verification failed due to an internal error.",
    )


async def export_backup(
    request: Request,
    backup_id: str,
    background_tasks: BackgroundTasks,
    api_context: ApiContext = Depends(resolve_api_context),
) -> FileResponse:
    validated_backup_id = resolve_validated_backup_id(request, backup_id)
    log_audit_event(
        request,
        AUDIT_BACKUP_EXPORT,
        "backup_manager",
        details={"backup_id": validated_backup_id},
    )
    backup_service = api_context.dependencies.backup_service
    if backup_service is None:
        raise_server_error(request, "Backup service is unavailable.")
    try:
        archive_path = await backup_service.create_backup_export_archive(validated_backup_id)
        background_tasks.add_task(os.remove, archive_path)
        return FileResponse(
            archive_path,
            media_type="application/gzip",
            filename=f"{validated_backup_id}.tar.gz",
            background=background_tasks,
        )
    except ConflictError as exception:
        raise_conflict(request, exception.message)
    except StateError as exception:
        raise_server_error(request, exception.message)
    except NotFoundError as exception:
        raise_not_found(request, exception.message)
    except ValidationError as exception:
        raise_invalid_request(request, exception.message)
    except InsufficientDiskSpaceError as exception:
        await raise_disk_space_api_error(
            request=request,
            exception=exception,
            operation="api_backup.export_backup",
            trace_id=get_request_trace_id(request),
            details={"backup_id": validated_backup_id},
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation="api_backup.export_backup")
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Backup export failed",
            operation=OPERATION_API_BACKUP_EXPORT_BACKUP,
            details={"backup_id": validated_backup_id},
        )
        raise_server_error(request, "Backup export failed due to an internal error.")


async def delete_backup(
    request: Request,
    backup_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    validated_backup_id = resolve_validated_backup_id(request, backup_id)
    log_audit_event(
        request,
        AUDIT_BACKUP_DELETE,
        "backup_manager",
        details={"backup_id": validated_backup_id},
    )
    backup_service = api_context.dependencies.backup_service
    if backup_service is None:
        raise_server_error(request, "Backup service is unavailable.")
    return await start_backup_task(
        request,
        validated_backup_id=validated_backup_id,
        user_id=current_user["id"],
        start_task=backup_service.start_delete_backup_task,
        operation=OPERATION_API_BACKUP_DELETE_BACKUP,
        failure_log_message="Backup deletion failed",
        failure_user_message="Backup deletion failed due to an internal error.",
    )


def register_endpoints(router: APIRouter) -> None:
    router.get(
        "",
        dependencies=require_action_dependencies(AccessAction.BACKUP_ADMIN),
    )(list_backups)
    router.post(
        "",
        status_code=202,
        dependencies=require_action_dependencies(AccessAction.BACKUP_ADMIN),
    )(create_backup)
    router.post(
        "/{backup_id}/restore",
        status_code=202,
        dependencies=require_action_dependencies(AccessAction.BACKUP_ADMIN),
    )(restore_backup)
    router.post(
        "/{backup_id}/verify",
        status_code=202,
        dependencies=require_action_dependencies(AccessAction.BACKUP_ADMIN),
    )(verify_backup)
    router.get(
        "/{backup_id}/export",
        dependencies=require_action_dependencies(AccessAction.BACKUP_ADMIN),
    )(export_backup)
    router.delete(
        "/{backup_id}",
        status_code=202,
        dependencies=require_action_dependencies(AccessAction.BACKUP_ADMIN),
    )(delete_backup)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.backup)
