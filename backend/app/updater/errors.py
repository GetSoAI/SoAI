"""SoAI - Updater argument validation and coercion [backend/app/updater/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import argparse
import dataclasses

from core.errors.exceptions import ValidationError
from core.tasks.identifiers import validate_optional_task_id

__all__ = (
    "UpdaterArgs",
    "parse_updater_args",
)


@dataclasses.dataclass(frozen=True, slots=True)
class UpdaterArgs:
    update_software: bool
    update_plugins: bool
    check_update_software: bool
    check_update_plugins: bool
    check_update_venv: bool
    port: int | None
    username: str | None
    password_stdin: bool
    config: str
    silent: bool
    no_restart: bool
    debug: bool
    wait_for_pid: int | None
    task_id: str | None = None


def parse_updater_args(namespace: argparse.Namespace) -> UpdaterArgs:
    if not isinstance(namespace, argparse.Namespace):
        raise ValidationError(
            "Updater args must be an argparse.Namespace.",
            details={"type": type(namespace).__name__},
        )
    try:
        config_value = namespace.config
    except AttributeError:
        config_value = None
    if not isinstance(config_value, str) or not config_value.strip():
        raise ValidationError(
            "Updater args must include a valid --config path.",
            details={"config": config_value},
        )
    try:
        port_value = namespace.port
    except AttributeError:
        port_value = None
    if port_value is not None and not isinstance(port_value, int):
        raise ValidationError(
            "Updater --port must be an int when provided.",
            details={"port": port_value},
        )
    try:
        username_value = namespace.username
    except AttributeError:
        username_value = None
    if username_value is not None and not isinstance(username_value, str):
        raise ValidationError(
            "Updater --username must be a str when provided.",
            details={"username": username_value},
        )
    normalized_username = (
        username_value.strip()
        if isinstance(username_value, str) and username_value.strip()
        else None
    )
    try:
        password_stdin_value = bool(namespace.password_stdin)
    except AttributeError:
        password_stdin_value = False
    if password_stdin_value and normalized_username is None:
        raise ValidationError("Updater --password-stdin requires --username.")
    try:
        wait_for_pid_value = namespace.wait_for_pid
    except AttributeError:
        wait_for_pid_value = None
    if wait_for_pid_value is not None and not isinstance(wait_for_pid_value, int):
        raise ValidationError(
            "Updater --wait-for-pid must be an int when provided.",
            details={"wait_for_pid": wait_for_pid_value},
        )
    try:
        task_id_value = namespace.task_id
    except AttributeError:
        task_id_value = None
    normalized_task_id = validate_optional_task_id(task_id_value, field_name="Updater --task-id")
    try:
        update_software_value = bool(namespace.update_software)
    except AttributeError:
        update_software_value = False
    try:
        update_plugins_value = bool(namespace.update_plugins)
    except AttributeError:
        update_plugins_value = False
    try:
        check_update_software_value = bool(namespace.check_update_software)
    except AttributeError:
        check_update_software_value = False
    try:
        check_update_plugins_value = bool(namespace.check_update_plugins)
    except AttributeError:
        check_update_plugins_value = False
    try:
        check_update_venv_value = bool(namespace.check_update_venv)
    except AttributeError:
        check_update_venv_value = False
    try:
        silent_value = bool(namespace.silent)
    except AttributeError:
        silent_value = False
    try:
        no_restart_value = bool(namespace.no_restart)
    except AttributeError:
        no_restart_value = False
    try:
        debug_value = bool(namespace.debug)
    except AttributeError:
        debug_value = False
    return UpdaterArgs(
        update_software=update_software_value,
        update_plugins=update_plugins_value,
        check_update_software=check_update_software_value,
        check_update_plugins=check_update_plugins_value,
        check_update_venv=check_update_venv_value,
        port=port_value,
        username=normalized_username,
        password_stdin=password_stdin_value,
        config=config_value,
        silent=silent_value,
        no_restart=no_restart_value,
        debug=debug_value,
        wait_for_pid=wait_for_pid_value,
        task_id=normalized_task_id,
    )
