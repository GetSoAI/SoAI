"""SoAI - Config save rollback after publish failure [backend/app/config/save_rollback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os

from filelock import Timeout

from app.config.internal_protocols import ConfigCacheProtocol, ConfigReconcilerProtocol
from app.config.save_outcome import ConfigSaveOutcome
from core.config.file_permissions import (
    runtime_config_atomic_file_mode,
    secure_runtime_config_paths,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConfigurationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.locking import async_guarded_file_lock
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.open_files import open_text
from core.logging.protocols import LoggerProtocol

__all__ = ("rollback_after_publish_failure",)

OPERATION = "config_manager.save_config"


async def rollback_after_publish_failure(
    outcome: ConfigSaveOutcome,
    *,
    reconciler: ConfigReconcilerProtocol,
    cache: ConfigCacheProtocol,
    logger: LoggerProtocol,
    in_file_lock: bool = False,
) -> None:
    def _on_timeout(_: Timeout) -> Exception:
        return ConfigurationError(f"Could not acquire lock to save {outcome.config_path}.")

    async def _restore_from_disk() -> None:
        if outcome.did_exist_before_save:
            await asyncio.to_thread(
                secure_runtime_config_paths,
                outcome.config_path,
                outcome.backup_path,
            )
            if not os.path.exists(outcome.backup_path):
                raise ConfigurationError(
                    f"Cannot rollback failed save for '{outcome.config_name}': missing backup at {outcome.backup_path}",
                )

            def _read_backup() -> str:
                with open_text(outcome.backup_path, encoding="utf-8") as handle:
                    return handle.read()

            backup_contents = await asyncio.to_thread(_read_backup)

            def _writer(handle: io.TextIOBase) -> None:
                handle.write(backup_contents)

            await asyncio.to_thread(
                atomic_write_text,
                outcome.config_path,
                _writer,
                mode="w",
                encoding="utf-8",
                backup_path=None,
                file_mode=runtime_config_atomic_file_mode(),
            )
            await asyncio.to_thread(
                secure_runtime_config_paths,
                outcome.config_path,
                outcome.backup_path,
            )
        elif os.path.exists(outcome.config_path):
            await asyncio.to_thread(os.remove, outcome.config_path)

    try:
        if in_file_lock:
            await _restore_from_disk()
        else:
            async with async_guarded_file_lock(
                outcome.lock_path,
                timeout=5,
                on_timeout=_on_timeout,
            ):
                await _restore_from_disk()
    except ConfigurationError as rollback_exception:
        log_exception(
            logger,
            rollback_exception,
            message="Failed to rollback config save after publish failure",
            operation=OPERATION,
            details={"config_name": outcome.config_name},
            level="critical",
        )
        raise
    except RECOVERABLE_EXCEPTIONS as rollback_exception:
        log_exception(
            logger,
            rollback_exception,
            message="Failed to rollback config save after publish failure",
            operation=OPERATION,
            details={"config_name": outcome.config_name},
            level="critical",
        )
        raise ConfigurationError(
            f"Failed to rollback failed save for '{outcome.config_name}': {rollback_exception}",
        ) from rollback_exception

    if outcome.previous_known_state is None:
        reconciler.known_files_state.pop(outcome.config_path, None)
    else:
        reconciler.known_files_state[outcome.config_path] = outcome.previous_known_state

    if outcome.previous_revision is None:
        reconciler.file_revisions.pop(outcome.config_path, None)
    else:
        reconciler.file_revisions[outcome.config_path] = outcome.previous_revision

    async with cache.lock:
        if outcome.previous_cached_snapshot is None:
            cache.configs.pop(outcome.config_name, None)
        else:
            cache.configs[outcome.config_name] = outcome.previous_cached_snapshot
