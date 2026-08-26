"""SoAI - CLI instance control PID helpers [backend/app/cli/instance_control_pid.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging

from core.bootstrap.runtime_record_path import resolve_runtime_record_path
from core.errors.exceptions import SoAIError
from core.runtime.instance_record import read_verified_runtime_instance_record

__all__ = (
    "read_running_pid",
    "resolve_pid_file_path",
)


def resolve_pid_file_path(base_dir: str, logger: logging.Logger) -> str:
    return resolve_runtime_record_path(base_dir, logger=logger)


def read_running_pid(
    base_dir: str,
    logger: logging.Logger,
    *,
    expected_edition: str,
) -> int | None:
    pid_file_path = resolve_pid_file_path(base_dir, logger)
    try:
        record = read_verified_runtime_instance_record(
            pid_file_path,
            base_dir=base_dir,
            expected_edition=expected_edition,
        )
    except (OSError, SoAIError) as exception:
        logger.error(
            "Runtime instance identity is unavailable for %s control: %s.",
            expected_edition,
            type(exception).__name__,
        )
        return None
    return record.pid if record is not None else None
