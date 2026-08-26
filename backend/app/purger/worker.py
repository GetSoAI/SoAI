"""SoAI - Recoverable restart purge worker [backend/app/purger/worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import os
import sys

from core.errors.exceptions import SoAIError, StateError
from core.files.managed_file_deletion import delete_managed_path
from core.files.managed_storage_errors import FileDeletionSecurityError
from core.filesystem.atomic_write_primitives import fsync_directory
from core.logging.configuration_constants import DEFAULT_LOG_DATE_FORMAT, DEFAULT_LOG_FORMAT
from core.logging.formatters import UnifiedFormatter
from core.restart_purge.transaction import (
    RestartPurgeManifest,
    load_restart_purge_transaction,
    update_restart_purge_manifest,
)

__all__ = ("resilient_purge", "run_restart_purge", "run_restart_purge_worker")

LOGGER_NAME = "SoAI.app.purger.worker"
PURGE_RETRY_ATTEMPTS = 5
PURGE_RETRY_DELAY_SECONDS = 2.0


async def resilient_purge(base_path: str, path_to_purge: str, logger: logging.Logger) -> bool:
    base_dir = os.path.realpath(os.path.abspath(base_path))
    path_abs = os.path.abspath(
        path_to_purge if os.path.isabs(path_to_purge) else os.path.join(base_dir, path_to_purge)
    )
    for attempt in range(1, PURGE_RETRY_ATTEMPTS + 1):
        try:
            deleted = await delete_managed_path(base_dir, path_abs)
            if deleted:
                logger.info("Restart purge deleted: %s", path_abs)
            else:
                logger.info("Restart purge target already absent: %s", path_abs)
            return True
        except FileDeletionSecurityError as exception:
            logger.critical(
                "Refusing unsafe restart purge path: %s",
                path_abs,
                exc_info=(type(exception), exception, exception.__traceback__),
            )
            return False
        except OSError as exception:
            if attempt == PURGE_RETRY_ATTEMPTS:
                logger.error(
                    "Restart purge could not delete %s after %d attempts.",
                    path_abs,
                    PURGE_RETRY_ATTEMPTS,
                    exc_info=(type(exception), exception, exception.__traceback__),
                )
                return False
            await asyncio.sleep(PURGE_RETRY_DELAY_SECONDS)
    return False


async def run_restart_purge(
    *,
    base_dir: str,
    sentinel_path: str,
    manifest_path: str,
    logger: logging.Logger,
) -> bool:
    _marker, manifest = load_restart_purge_transaction(
        sentinel_path=sentinel_path,
        manifest_path=manifest_path,
    )
    if manifest.state == "succeeded":
        _commit_success(sentinel_path=sentinel_path, manifest_path=manifest_path)
        return True
    remaining = list(manifest.paths_to_delete)
    failed: list[str] = []
    for path in tuple(remaining):
        if await resilient_purge(base_dir, path, logger):
            remaining.remove(path)
            update_restart_purge_manifest(
                manifest_path,
                RestartPurgeManifest(
                    state="pending",
                    paths_to_delete=tuple(remaining),
                    failed_paths=tuple(failed),
                ),
            )
        else:
            failed.append(path)
    if remaining:
        update_restart_purge_manifest(
            manifest_path,
            RestartPurgeManifest(
                state="failed",
                paths_to_delete=tuple(remaining),
                failed_paths=tuple(failed),
            ),
        )
        logger.error("Restart purge retained %d path(s) for recovery.", len(remaining))
        return False
    update_restart_purge_manifest(
        manifest_path,
        RestartPurgeManifest(state="succeeded", paths_to_delete=(), failed_paths=()),
    )
    _commit_success(sentinel_path=sentinel_path, manifest_path=manifest_path)
    logger.info("Restart purge transaction committed successfully.")
    return True


def _commit_success(*, sentinel_path: str, manifest_path: str) -> None:
    os.unlink(sentinel_path)
    fsync_directory(os.path.dirname(sentinel_path))
    os.unlink(manifest_path)
    fsync_directory(os.path.dirname(manifest_path))


def _configure_worker_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(
        UnifiedFormatter(
            DEFAULT_LOG_FORMAT,
            DEFAULT_LOG_DATE_FORMAT,
            use_colors=False,
        ),
    )
    previous_handlers = list(logger.handlers)
    logger.handlers = [handler]
    for previous_handler in previous_handlers:
        previous_handler.close()
    return logger


async def run_restart_purge_worker() -> int:
    if len(sys.argv) != 4:
        raise StateError("Restart purger requires base, sentinel, and manifest paths.")
    base_dir = os.path.abspath(sys.argv[1])
    logger = _configure_worker_logging()
    try:
        succeeded = await run_restart_purge(
            base_dir=base_dir,
            sentinel_path=os.path.abspath(sys.argv[2]),
            manifest_path=os.path.abspath(sys.argv[3]),
            logger=logger,
        )
    except (OSError, SoAIError, ValueError) as exception:
        logger.critical(
            "Restart purge transaction failed.",
            exc_info=(type(exception), exception, exception.__traceback__),
        )
        return 1
    return 0 if succeeded else 1
