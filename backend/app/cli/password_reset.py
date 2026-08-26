"""SoAI - Admin password reset CLI utility [backend/app/cli/password_reset.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import getpass
import logging
import os
import threading
from collections.abc import Awaitable, Callable

from ruamel.yaml import YAML

from app.cli.offline_mode import resolve_config_path
from app.config.schema_disk_reconciliation import coerce_config_yaml_mapping
from core.concurrency.protocols import CancellationTokenProtocol
from core.config.runtime_config import Config
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventCompletionSignal
from core.events.types_base import Event
from core.filesystem.open_files import open_text
from core.logging.bootstrap import setup_bootstrap_logger
from core.logging.protocols import LoggerProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.runtime.event_loop_runner import run_coroutine_in_new_event_loop
from core.security.password_hashing import PasswordContext
from core.tasks.type_catalog import TaskTypeCatalog
from core.timing.constants import YIELD_CONTROL_SEC
from core.types.json import JSONValue
from core.users.protocols_database import DatabaseUsersProtocol
from core.users.username import require_canonical_username
from database.core.factory import create_database_core
from database.repositories.dependencies import DatabaseRepositoryDependencies
from database.repositories.users.users import DatabaseUsers

__all__ = ("run_password_reset",)

OPERATION_APP_CLI_CREDENTIAL_RESET = "app.cli.password_reset"


class _NoopEventBus:
    def __init__(self) -> None:
        self.metrics_recorder: MetricsManagerProtocol | None = None
        self.shutdown_event = asyncio.Event()

    def subscribe(
        self,
        event_type: type[Event],
        callback: Callable[[Event], Awaitable[None]],
    ) -> None:
        del event_type, callback

    def unsubscribe(
        self,
        event_type: type[Event],
        callback: Callable[[Event], Awaitable[None]],
    ) -> None:
        del event_type, callback

    def has_subscribers(self, event_type: type[Event]) -> bool:
        del event_type
        return False

    async def publish(
        self,
        event: Event,
        wait_for_completion: EventCompletionSignal | None = None,
    ) -> None:
        del event, wait_for_completion

    def try_publish_nowait(
        self,
        event: Event,
        wait_for_completion: EventCompletionSignal | None = None,
    ) -> bool:
        del event, wait_for_completion
        return True

    def start(self) -> None:
        return

    async def shutdown(self) -> None:
        return

    def set_metrics_recorder(self, recorder: MetricsManagerProtocol | None) -> None:
        self.metrics_recorder = recorder


class _NoopCancellationToken:
    def __init__(
        self,
        *,
        cancellation_id: str,
        owner: str,
        metadata: dict[str, JSONValue] | None,
    ) -> None:
        self.cancellation_id = cancellation_id
        self.owner = owner
        self.metadata = dict(metadata) if metadata is not None else {}
        self.thread_event = threading.Event()
        self.cancellation_reason: str | None = None

    async def wait(self) -> None:
        await asyncio.sleep(YIELD_CONTROL_SEC)

    def is_cancelled(self) -> bool:
        return False

    def raise_if_cancelled(self) -> None:
        return

    def cancel(self, reason: str) -> bool:
        del reason
        return False


class _NoopTaskCancellationBinder:
    async def bind_task[TaskResult](
        self,
        cancellation_id: str,
        task: asyncio.Task[TaskResult],
        *,
        owner: str,
        metadata: dict[str, JSONValue] | None = None,
    ) -> CancellationTokenProtocol:
        del task
        return _NoopCancellationToken(
            cancellation_id=cancellation_id,
            owner=owner,
            metadata=metadata,
        )


class _NoopTaskFinalizerTracker:
    def track_finalizer(self, task: asyncio.Task[None]) -> None:
        del task

    async def await_all_finalizers(
        self,
        *,
        timeout: float = 5.0,
        logger: LoggerProtocol | None = None,
    ) -> bool:
        del timeout, logger
        return True


def run_password_reset(
    username: str,
    *,
    base_dir: str,
    task_catalog: TaskTypeCatalog,
) -> None:
    logger = setup_bootstrap_logger("SoAI.CLI.PasswordReset", level=logging.INFO)
    cancellation_binder = _NoopTaskCancellationBinder()
    finalizer_tracker = _NoopTaskFinalizerTracker()

    async def _async_reset_password(
        database_path: str,
        target_username: str,
        hashed_password: str,
        config: Config,
    ) -> tuple[bool, str | None]:
        canonical_username = require_canonical_username(target_username)
        database_core_instance = await create_database_core(
            config=config,
            database_path=database_path,
            logger=logger,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            metrics_recorder=None,
            task_catalog=task_catalog,
        )
        database_users_instance: DatabaseUsersProtocol = DatabaseUsers(
            DatabaseRepositoryDependencies(
                core=database_core_instance,
                config=config,
                fernet=(),
                event_bus=_NoopEventBus(),
            ),
        )
        try:
            user = await database_users_instance.get_human_user_by_username(canonical_username)
            if user is None:
                return (False, f"User '{target_username}' not found in the database.")
            success = await database_users_instance.update_user_password(
                canonical_username,
                hashed_password,
            )
            if success:
                return (True, None)
            return (
                False,
                f"Failed to update password for user '{target_username}'. No rows affected.",
            )
        finally:
            await database_core_instance.vacuum.shutdown()
            await database_core_instance.reader.shutdown()
            await database_core_instance.writer.shutdown()

    logger.info("--- SoAI: Admin Password Reset Utility ---")
    try:
        config_path = resolve_config_path(base_dir)
        with open_text(config_path, encoding="utf-8") as file_handle:
            config_data = YAML(typ="safe").load(file_handle)
        config_payload = coerce_config_yaml_mapping(config_data or {}, config_path=config_path)
        config = Config(config_payload, main_app_base_dir=base_dir)
        database_path_str = config.get_str("DATA.DATABASE.PATHS.SYSTEM_DB")
        if database_path_str is None or not database_path_str.strip():
            raise SystemExit("ERROR: DATA.DATABASE.PATHS.SYSTEM_DB is missing from configuration.")
        candidate_db_path = (
            database_path_str
            if os.path.isabs(database_path_str)
            else os.path.join(base_dir, database_path_str)
        )
        database_path = os.path.abspath(candidate_db_path)
        if not os.path.exists(database_path):
            raise SystemExit(
                f"ERROR: Database file not found at the configured path: '{database_path}'.",
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        raise SystemExit(
            f"ERROR: Could not read configuration to find database: {exception}",
        ) from exception
    new_password = getpass.getpass("Enter new password: ")
    if new_password != getpass.getpass("Confirm new password: "):
        raise SystemExit("Passwords do not match. Aborting.")
    if len(new_password) < 8:
        raise SystemExit("Password must be at least 8 characters. Aborting.")
    hashed_password = PasswordContext().hash(new_password)
    try:
        success, error_message = run_coroutine_in_new_event_loop(
            _async_reset_password(database_path, username, hashed_password, config),
        )
        if success:
            logger.info(
                "Successfully reset password for user '%s'. All previous sessions have been invalidated.",
                username,
            )
        else:
            raise SystemExit(f"ERROR: {error_message}")
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="An error occurred during the database operation.",
            operation=OPERATION_APP_CLI_CREDENTIAL_RESET,
        )
        raise SystemExit(1) from exception
