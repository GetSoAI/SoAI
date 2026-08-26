"""SoAI - Backup task start flow [backend/features/api/routes/backups/task_starter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    NotFoundError,
    SecurityError,
    StateError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from features.api.routes.backups.internal_protocols import BackupTaskStarterProtocol
from features.api.runtime.context import get_request_trace_id
from features.api.runtime.errors import (
    raise_invalid_request,
    raise_not_found,
    raise_server_error,
)
from features.api.runtime.responses import create_task_accepted_response
from features.api.runtime.task_api_errors import raise_disk_space_api_error

__all__ = ("start_backup_task",)

OPERATION_FEATURES_API_ROUTES_BACKUPS_TASK_STARTER_START_BACKUP_TASK = (
    "features.api.routes.backups.task_starter.start_backup_task"
)


LOGGER_NAME = "SoAI.features.api.task_starter"


async def start_backup_task(
    request: Request,
    *,
    validated_backup_id: str,
    user_id: int,
    start_task: BackupTaskStarterProtocol,
    operation: str,
    failure_log_message: str,
    failure_user_message: str,
) -> JSONResponse:
    try:
        task_id = await start_task(validated_backup_id, user_id=user_id)
        return create_task_accepted_response(task_id=task_id, commit_deadline_ts_ms=None)
    except StateError as exception:
        raise_server_error(request, exception.message)
    except NotFoundError as exception:
        raise_not_found(request, exception.message)
    except ValidationError as exception:
        raise_invalid_request(request, exception.message)
    except SecurityError as exception:
        raise_invalid_request(request, exception.message)
    except InsufficientDiskSpaceError as exception:
        await raise_disk_space_api_error(
            request=request,
            exception=exception,
            operation=operation,
            trace_id=get_request_trace_id(request),
            details={"backup_id": validated_backup_id},
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message=failure_log_message,
            operation=OPERATION_FEATURES_API_ROUTES_BACKUPS_TASK_STARTER_START_BACKUP_TASK,
            details={"backup_id": validated_backup_id},
        )
        raise_server_error(request, failure_user_message)
    raise StateError(
        "Backup task start helper did not raise or return.",
        operation="api_backup.task_start_helper",
    )
