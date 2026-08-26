"""SoAI - Updater local version detection [backend/app/updater/service_version_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re

from app.application_dependencies import ApplicationUpdaterModuleDependencies
from app.updater.version_paths import resolve_version_py_path
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.open_files import open_text
from core.logging.protocols import LoggerProtocol

__all__ = ("detect_local_version",)

OPERATION = "application_updater.get_local_version"


def detect_local_version(
    *,
    module_dependencies: ApplicationUpdaterModuleDependencies,
    logger: LoggerProtocol,
    base_path: str,
    main_py_path: str | None,
) -> str | None:
    if not main_py_path:
        logger.warning("Main application path is not initialized.")
        return None
    version_py_path = resolve_version_py_path(base_path)
    if not os.path.exists(version_py_path):
        logger.warning(
            "Could not find version.py at '%s' to determine local version.",
            version_py_path,
        )
        return None
    try:
        with open_text(version_py_path, encoding="utf-8") as file_handle:
            content = file_handle.read()
        match = re.search("^__version__\\s*=\\s*['\\\"]([^'\\\"]+)['\\\"]", content, re.MULTILINE)
        if match is None:
            logger.warning("Could not find __version__ string in version.py.")
            return None
        version_str = match.group(1)
        try:
            normalized = module_dependencies.normalize_version_string(version_str)
        except (ValidationError, ValueError) as exception:
            log_exception(
                logger,
                exception,
                message=f"Invalid local version '{version_str}'.",
                operation=OPERATION,
                level="error",
            )
            return None
        logger.info("Detected local SoAI version: v%s", normalized)
        return normalized
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to read or parse version.py for version.",
            operation=OPERATION,
            level="error",
        )
        return None
