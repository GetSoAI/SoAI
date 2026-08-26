"""SoAI - Shared storage-backed repository runtime helpers [backend/database/repositories/users/storage_backed_repository_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.files.storage_root_resolution import resolve_managed_files_storage_root

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = (
    "queue_storage_backed_write",
    "resolve_storage_backed_repository_root",
)


async def queue_storage_backed_write[*Ts, T](
    core: DatabaseCoreProtocol,
    func: Callable[[sqlite3.Connection, *Ts], T],
    *args: *Ts,
) -> T:
    return await core.writer.queue_write_operation(func, *args)


def resolve_storage_backed_repository_root(
    deps: DatabaseRepositoryDependencies,
) -> str | None:
    if deps.files is None:
        return None
    return resolve_managed_files_storage_root(deps.config, deps.files)
