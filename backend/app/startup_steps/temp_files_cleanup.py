"""SoAI - Startup temporary file cleanup [backend/app/startup_steps/temp_files_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import re
import shutil
from dataclasses import dataclass

from app.startup_steps.dependencies import StartupStepDependencies
from app.types_application import ApplicationContext
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.operations import async_remove
from core.files.path_policy import safe_join_relative_under_base_lexical
from core.filesystem.async_queries import async_isdir, async_islink, async_listdir
from core.timing.epoch import epoch_seconds_float
from mcp.tools.shell_transcript_paths import SHELL_TRANSCRIPT_TEMP_DIRNAME

__all__ = ("TempFilesCleanupStep",)

OPERATION = "application_startup.cleanup_temp_files"


@dataclass(frozen=True, slots=True)
class TempFilesCleanupStep:
    deps: StartupStepDependencies

    async def cleanup_temp_files(self, application_context: ApplicationContext) -> None:
        logging_context = application_context.logging
        logging_context.lifecycle_logger.debug("Scanning for leftover temporary files...")
        paths_to_scan: list[str] = []
        seen_paths: set[str] = set()

        def add_scan_path(candidate: str | None) -> None:
            if not candidate:
                return
            normalized = os.path.abspath(candidate)
            if normalized not in seen_paths:
                seen_paths.add(normalized)
                paths_to_scan.append(normalized)

        add_scan_path(os.path.dirname(application_context.paths.config_path))
        add_scan_path(application_context.paths.plugin_directory)

        configuration = application_context.services.configuration.config
        if configuration is not None:
            temp_path = configuration.get_str("SYSTEM.PATHS.TEMP")
            resolved_temp: str | None = None
            try:
                config_files = application_context.services.configuration.files
                if config_files is not None and isinstance(temp_path, str) and temp_path:
                    resolved_temp = config_files.resolve_path(temp_path)
                elif isinstance(temp_path, str) and temp_path:
                    resolved_temp = temp_path
            except RECOVERABLE_EXCEPTIONS as error:
                log_handled_exception(
                    logging_context.lifecycle_logger,
                    error,
                    message="Failed to resolve temporary path (non-critical).",
                    operation=OPERATION,
                    details={"temp_path": temp_path},
                    level="debug",
                )
                resolved_temp = None
            add_scan_path(resolved_temp)

        plugin_manager_instance = application_context.services.plugins.plugin_manager
        if plugin_manager_instance is not None:
            try:
                plugin_paths = plugin_manager_instance.paths
            except AttributeError:
                plugin_paths = None
            if plugin_paths is not None:
                add_scan_path(plugin_paths.temp_directory)

        updater_script_pattern = re.compile(r"^updater_new_\d{14}\.py$")
        updater_payload_pattern = re.compile(r"^update_payload_\d{14}\.zip$")
        staged_upload_pattern = re.compile(r"^tmp[a-z0-9_]+_")
        multipart_staged_upload_pattern = re.compile(r"^tmpupload_multipart_")
        file_explorer_archive_pattern = re.compile(
            r"^soai-file-explorer-[a-z0-9_]+\.zip$",
        )
        file_explorer_listing_pattern = re.compile(
            r"^soai-file-listing-[a-z0-9_]+\.sqlite3$",
        )

        def should_cleanup(filename: str) -> bool:
            if filename == SHELL_TRANSCRIPT_TEMP_DIRNAME:
                return True
            if ".tmp." in filename:
                return True
            if staged_upload_pattern.match(filename):
                return True
            if file_explorer_archive_pattern.match(filename):
                return True
            if file_explorer_listing_pattern.match(filename):
                return True
            return bool(
                updater_script_pattern.match(filename) or updater_payload_pattern.match(filename),
            )

        for directory_path in paths_to_scan:
            if not await async_isdir(directory_path):
                continue
            try:
                for filename in await async_listdir(directory_path):
                    if not should_cleanup(filename):
                        continue
                    full_path = safe_join_relative_under_base_lexical(
                        base_path=directory_path,
                        relative_path=filename,
                        description="Temporary cleanup path",
                    )
                    try:
                        is_file_explorer_session_file = bool(
                            file_explorer_archive_pattern.match(filename)
                            or file_explorer_listing_pattern.match(filename),
                        )
                        if (
                            filename == SHELL_TRANSCRIPT_TEMP_DIRNAME
                            or multipart_staged_upload_pattern.match(filename)
                            or is_file_explorer_session_file
                            or epoch_seconds_float()
                            - await asyncio.to_thread(os.path.getmtime, full_path)
                            > 3600
                        ):
                            if await async_isdir(full_path) and not await async_islink(
                                full_path,
                            ):
                                await asyncio.to_thread(shutil.rmtree, full_path)
                            else:
                                await async_remove(full_path)
                            logging_context.lifecycle_logger.warning(
                                "Removed stale temporary file: %s",
                                full_path,
                            )
                    except FileNotFoundError:
                        continue
                    except OSError as exception:
                        log_exception(
                            logging_context.lifecycle_logger,
                            exception,
                            message="Failed to process or remove temp file",
                            operation=OPERATION,
                            details={"path": full_path},
                        )
            except PermissionError as exception:
                logging_context.lifecycle_logger.critical(
                    "Fatal permission error during temp file cleanup in %s: %s. Cannot continue startup.",
                    directory_path,
                    str(exception),
                )
                self.deps.runtime_coordinator.fail_startup(
                    f"Permission error during temp file cleanup in {directory_path}.",
                )
            except OSError as exception:
                log_exception(
                    logging_context.lifecycle_logger,
                    exception,
                    message="Error listing files during temp file cleanup",
                    operation=OPERATION,
                    details={"dir_path": directory_path},
                )
