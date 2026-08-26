"""SoAI - Database core factory helpers [backend/database/core/factory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseMetricsRecorderProtocol
from core.logging.protocols import StandardLogger
from core.tasks.type_catalog import TaskTypeCatalog
from database.core.core import DatabaseCore
from database.core.feature_gate import DatabaseFeatureGate
from database.core.manager_config import resolve_database_manager_settings
from database.core.paths import resolve_database_paths
from database.core.reader import DatabaseReader, DatabaseReaderDependencies
from database.core.vacuum_runtime import DatabaseVacuum, DatabaseVacuumDependencies
from database.core.writer import DatabaseWriter, DatabaseWriterDependencies

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = ("create_database_core",)


async def create_database_core(
    *,
    config: ConfigProtocol,
    database_path: str,
    logger: StandardLogger,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    metrics_recorder: DatabaseMetricsRecorderProtocol | None = None,
    task_catalog: TaskTypeCatalog,
) -> DatabaseCore:
    paths = resolve_database_paths(database_path)
    settings = resolve_database_manager_settings(config, logger=logger)
    feature_gate = DatabaseFeatureGate()
    writer = DatabaseWriter(
        DatabaseWriterDependencies(
            paths=paths,
            config=config,
            settings=settings,
            metrics_recorder=metrics_recorder,
            task_catalog=task_catalog,
        ),
    )
    await writer.initialize()
    reader = DatabaseReader(
        DatabaseReaderDependencies(
            paths=paths,
            writer=writer,
            connect_timeout=settings.sqlite_connect_timeout,
            max_pool_size=settings.read_pool_max_size,
            read_mmap_size_mb=settings.read_mmap_size_mb,
        ),
    )
    vacuum = DatabaseVacuum(
        DatabaseVacuumDependencies(
            paths=paths,
            writer=writer,
            vacuum_interval_hours=settings.vacuum_interval_hours,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
        ),
    )
    return DatabaseCore(
        reader=reader,
        writer=writer,
        vacuum=vacuum,
        features=feature_gate,
    )
