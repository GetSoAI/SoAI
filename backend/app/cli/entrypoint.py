"""SoAI - Lightweight CLI lifecycle entrypoint [backend/app/cli/entrypoint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
import sys

from app.cli.instance_control import handle_restart, handle_status, handle_stop
from app.cli.restart_purge import handle_restart_purge_sentinel
from app.cli.startup_flags import (
    apply_environment_flags,
    build_argument_parser,
    handle_information_cli_request,
    normalize_cli_args,
    resolve_startup_action,
)
from core.bootstrap.install_payload import validate_existing_install_edition
from core.errors.exceptions import ValidationError
from core.logging.bootstrap import setup_bootstrap_logger
from core.meta.paths import get_repo_root
from core.runtime.opencl_environment import configure_opencl_runtime_environment
from core.system.process_replacement import replace_current_process
from core.validation.runtime import ensure_minimum_python_version

__all__ = ("cli_entrypoint",)

CREDENTIAL_RESET_ENTRYPOINT_MODULE = "app.cli.password_reset_entrypoint"


def _exec_cli_module(
    module_name: str,
    arguments: list[str],
    logger: logging.Logger,
) -> int:
    command = [sys.executable, "-m", module_name, *arguments]
    try:
        return replace_current_process(command)
    except (OSError, ValueError) as exception:
        logger.critical(
            "FATAL: Failed to exec CLI module %s: %s: %s",
            module_name,
            type(exception).__name__,
            exception,
        )
        return 1


def _dispatch_lifecycle_action(
    action: str,
    *,
    base_dir: str,
    username: str,
    normalized_args: list[str],
    logger: logging.Logger,
    runtime_entrypoint_module: str,
    restart_cli_module: str,
    password_reset_cli_module: str,
    expected_edition: str,
) -> int | None:
    if action == "install_deps":
        return 0
    if action == "restart":
        return handle_restart(
            base_dir,
            logger,
            restart_cli_module=restart_cli_module,
            expected_edition=expected_edition,
        )
    if action == "stop":
        return handle_stop(base_dir, logger, expected_edition=expected_edition)
    if action == "status":
        return handle_status(base_dir, logger, expected_edition=expected_edition)
    if action == "password_reset":
        return _exec_cli_module(
            password_reset_cli_module,
            ["--username", username],
            logger,
        )
    if action == "start":
        return _exec_cli_module(runtime_entrypoint_module, normalized_args, logger)
    logger.critical("FATAL: Unknown CLI startup action: %s", action)
    return 2


def cli_entrypoint(
    arguments: list[str] | None = None,
    *,
    runtime_entrypoint_module: str = "app.cli.runtime_entrypoint",
    restart_cli_module: str = "app.cli.entrypoint",
    password_reset_cli_module: str = CREDENTIAL_RESET_ENTRYPOINT_MODULE,
    expected_edition: str = "soai-core",
) -> int | None:
    provided_args = list(sys.argv[1:] if arguments is None else arguments)
    information_exit_code = handle_information_cli_request(
        provided_args,
        program_name=os.path.basename(sys.argv[0]),
    )
    if information_exit_code is not None:
        return information_exit_code
    ensure_minimum_python_version()
    configure_opencl_runtime_environment()
    bootstrap_logger = setup_bootstrap_logger("SoAI.Bootstrap")
    program_name = sys.argv[0]
    normalized_args = normalize_cli_args(provided_args)
    sys.argv = [program_name] + normalized_args

    base_dir = get_repo_root()
    try:
        validate_existing_install_edition(base_dir, expected_edition)
    except ValidationError as exception:
        bootstrap_logger.critical("FATAL: %s", exception)
        return 2
    sentinel_path = os.path.join(base_dir, "restart_purge.sentinel")
    manifest_path = os.path.join(base_dir, "restart_purge.manifest.json")
    handle_restart_purge_sentinel(
        base_dir,
        sentinel_path=sentinel_path,
        manifest_path=manifest_path,
        logger=bootstrap_logger,
    )

    parser = build_argument_parser()
    parsed_args = parser.parse_args(normalized_args)
    action = resolve_startup_action(parsed_args)
    apply_environment_flags(parsed_args)
    return _dispatch_lifecycle_action(
        action,
        base_dir=base_dir,
        username=str(parsed_args.reset_user_password or ""),
        normalized_args=normalized_args,
        logger=bootstrap_logger,
        runtime_entrypoint_module=runtime_entrypoint_module,
        restart_cli_module=restart_cli_module,
        password_reset_cli_module=password_reset_cli_module,
        expected_edition=expected_edition,
    )


if __name__ == "__main__":
    raise SystemExit(cli_entrypoint() or 0)
