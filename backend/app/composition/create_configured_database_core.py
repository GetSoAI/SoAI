"""SoAI - Configured database core creation [backend/app/composition/create_configured_database_core.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.logging.protocols import TraceLogger
from core.plugins.protocols_instance import FilesProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.tasks.type_catalog import TaskTypeCatalog
from database.core.core import DatabaseCore
from database.core.factory import create_database_core

__all__ = ("create_configured_database_core",)


async def create_configured_database_core(
    *,
    config: ConfigProtocol,
    files: FilesProtocol,
    logger: TraceLogger,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    task_catalog: TaskTypeCatalog,
) -> DatabaseCore:
    database_path_value = config.get_str("DATA.DATABASE.PATHS.SYSTEM_DB")
    if not database_path_value:
        raise ValidationError("DATA.DATABASE.PATHS.SYSTEM_DB must be configured.")
    return await create_database_core(
        config=config,
        database_path=files.resolve_path(database_path_value),
        logger=logger,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        metrics_recorder=None,
        task_catalog=task_catalog,
    )
