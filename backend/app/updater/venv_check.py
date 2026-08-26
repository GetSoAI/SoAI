"""SoAI - Updater venv update check [backend/app/updater/venv_check.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

from core.bootstrap.venv_paths import get_venv_path, get_venv_python_executable
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.open_files import open_text
from core.logging.protocols import LoggerProtocol
from core.serialization.json_parsing import parse_json_value
from core.system.commands import run_argv_capture
from core.types.json import is_json_dict, is_json_list

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("check_venv_updates",)

OPERATION_APPLICATION_UPDATER_CHECK_VENV = "application_updater.check_venv"
OPERATION_APPLICATION_UPDATER_CHECK_VENV_CHECK_PACKAGES = (
    "application_updater.check_venv.check_packages"
)
OPERATION_APPLICATION_UPDATER_CHECK_VENV_PARSE_REQUIREMENTS = (
    "application_updater.check_venv.parse_requirements"
)


def _parse_requirement_names(requirements_text: str) -> set[str]:
    names: set[str] = set()
    for raw_line in requirements_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        line = stripped.split("#", maxsplit=1)[0].strip()
        if not line:
            continue
        match = re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*", line)
        if match:
            names.add(match.group(0).lower())
    return names


def _extract_outdated_core_dependencies(
    payload: JSONValue,
    core_dependency_names: set[str],
) -> list[JSONDict]:
    if not is_json_list(payload):
        raise ValueError("pip outdated payload must be a JSON list.")
    matched: list[JSONDict] = []
    for package in payload:
        if not is_json_dict(package):
            continue
        name_value = package.get("name")
        if isinstance(name_value, str) and name_value.lower() in core_dependency_names:
            matched.append(package)
    return matched


def check_venv_updates(
    *,
    base_path: str,
    logger: LoggerProtocol,
) -> int:
    logger.info("%s\nChecking for SoAI Venv Updates\n%s", "=" * 60, "=" * 60)
    try:
        venv_path = get_venv_path(base_path)
        requirements_path = os.path.join(base_path, "requirements.txt")
        if not os.path.exists(requirements_path):
            logger.warning("Could not find requirements.txt at '%s'.", requirements_path)
            return 1
        with open_text(requirements_path, encoding="utf-8") as file_handle:
            requirements_text = file_handle.read()
        core_dependency_names = _parse_requirement_names(requirements_text)
        if not core_dependency_names:
            logger.warning("requirements.txt contains no dependency entries.")
            return 1
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to read requirements.txt for venv update check.",
            operation=OPERATION_APPLICATION_UPDATER_CHECK_VENV_PARSE_REQUIREMENTS,
            level="error",
        )
        return 1
    py_exe = get_venv_python_executable(venv_path)
    if not os.path.exists(py_exe):
        logger.warning("SoAI venv python not found at '%s'.", py_exe)
        return 1
    logger.info("Using venv python: %s\nChecking for outdated core deps...", py_exe)
    try:
        result = run_argv_capture(
            [py_exe, "-m", "pip", "list", "--outdated", "--format=json"],
            timeout=60,
            check=True,
        )
        parsed_payload: JSONValue = parse_json_value(result.stdout)
        outdated_core_deps = _extract_outdated_core_dependencies(
            parsed_payload,
            core_dependency_names,
        )
    except (CalledProcessError, ValidationError, ValueError) as exception:
        log_exception(
            logger,
            exception,
            message="Failed to check packages via pip",
            operation=OPERATION_APPLICATION_UPDATER_CHECK_VENV,
        )
        return 1
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="An unexpected error occurred while checking packages.",
            operation=OPERATION_APPLICATION_UPDATER_CHECK_VENV_CHECK_PACKAGES,
            level="error",
        )
        return 1
    if not outdated_core_deps:
        logger.info("\nStatus: All SoAI core dependencies are up-to-date!")
        return 0
    logger.warning("\nStatus: Updates are available for some SoAI core dependencies:")
    for pkg in outdated_core_deps:
        package_name = str(pkg.get("name") or "unknown")
        package_version = str(pkg.get("version") or "?")
        package_latest_version = str(pkg.get("latest_version") or "?")
        logger.warning(
            "  - %-20s: %s -> %s",
            package_name,
            package_version,
            package_latest_version,
        )
    logger.info(
        "\nTo update, run the main SoAI application (main.py) to trigger the bootstrap process.",
    )
    return 0
