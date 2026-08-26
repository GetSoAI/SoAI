"""SoAI - Config baseline update workflow [backend/app/config/baseline_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.config.internal_protocols import (
    ConfigCacheProtocol,
    ConfigIOProtocol,
    ConfigReconcilerProtocol,
)
from core.config.locks import get_lock_path
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConfigurationError, SoAITimeoutError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.lock_acquisition_retry import async_retrying_guarded_file_lock
from core.logging.protocols import LoggerProtocol

__all__ = (
    "ConfigBaselineUpdater",
    "ConfigBaselineUpdaterDependencies",
)

OPERATION = "config_manager.rescan_and_update_baseline_for_config"
LOCK_OPERATION = "config_manager.rescan_and_update_baseline_for_config.acquire_lock"
_LOCK_TIMEOUT_SECONDS = 5.0
_LOCK_EXHAUSTED_MESSAGE = "Timed out waiting for the configuration baseline lock."


@dataclass(frozen=True, slots=True)
class ConfigBaselineUpdaterDependencies:
    logger: LoggerProtocol
    io_lock_directory: str | None
    reconciler: ConfigReconcilerProtocol
    io: ConfigIOProtocol
    cache: ConfigCacheProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ConfigBaselineUpdaterDependencies",
            cache=self.cache,
            io=self.io,
            logger=self.logger,
            reconciler=self.reconciler,
        )


class ConfigBaselineUpdater:
    def __init__(self, deps: ConfigBaselineUpdaterDependencies) -> None:
        self._deps = deps

    async def _capture_locked_snapshot(
        self,
        *,
        config_name: str,
        config_path: str,
        lock_path: str,
    ) -> None:
        async with async_retrying_guarded_file_lock(
            lock_path,
            timeout_seconds=_LOCK_TIMEOUT_SECONDS,
            operation=LOCK_OPERATION,
            exhausted_message=_LOCK_EXHAUSTED_MESSAGE,
        ):
            config_mapping, known_state = (
                await self._deps.io.read_config_baseline_snapshot_unlocked(
                    config_path=config_path,
                    config_name=config_name,
                )
            )
            await self._deps.cache.set(config_name, config_mapping)
            self._deps.reconciler.known_files_state[config_path] = known_state
            self._deps.reconciler.ensure_revision_initialized(config_path)

    async def update_baseline_for_config(self, *, config_name: str, config_path: str) -> None:
        self._deps.logger.debug("Performing authoritative baseline update for '%s'", config_path)
        lock_path = get_lock_path(config_path, lock_directory=self._deps.io_lock_directory)

        try:
            async with self._deps.reconciler.reconciliation_lock:
                await self._capture_locked_snapshot(
                    config_name=config_name,
                    config_path=config_path,
                    lock_path=lock_path,
                )
            self._deps.logger.debug(
                "Successfully updated baseline for '%s' after a programmatic change.",
                config_name,
            )
        except FileNotFoundError:
            self._deps.logger.warning(
                "Tried to update baseline for '%s', but file does not exist. Removing from baseline.",
                config_name,
            )
            self._deps.reconciler.known_files_state.pop(config_path, None)
            self._deps.reconciler.file_revisions.pop(config_path, None)
        except RECOVERABLE_EXCEPTIONS as exception:
            if isinstance(exception, SoAITimeoutError):
                raise
            log_exception(
                self._deps.logger,
                exception,
                message="Failed to update baseline",
                operation=OPERATION,
                details={"config_name": config_name},
            )
            raise ConfigurationError(
                f"Failed to update baseline for '{config_name}': {exception}",
            ) from exception
