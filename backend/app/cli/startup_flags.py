"""SoAI - CLI flag definition and startup action resolution [backend/app/cli/startup_flags.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING, Literal

from core.bootstrap.install_deps_flags import (
    INSTALL_DEPS_BARE_COMMAND,
    INSTALL_DEPS_LONG_OPTION,
    INSTALL_DEPS_SHORT_OPTION,
)
from core.meta.version import __version__

if TYPE_CHECKING:
    type StartupAction = Literal[
        "install_deps",
        "restart",
        "stop",
        "status",
        "password_reset",
        "start",
    ]

__all__ = (
    "apply_environment_flags",
    "build_argument_parser",
    "handle_information_cli_request",
    "normalize_cli_args",
    "resolve_startup_action",
)


def normalize_cli_args(raw_args: list[str]) -> list[str]:
    normalized: list[str] = []
    expects_value_for: str | None = None

    value_options = {
        "-reset-user-password",
        "--reset-user-password",
    }
    bare_to_option = {
        "reset-user-password": "--reset-user-password",
        "help": "--help",
        "version": "--version",
        "start-no-browser": "--start-no-browser",
        "verbose": "--verbose",
        "restart": "--restart",
        "stop": "--stop",
        "status": "--status",
        INSTALL_DEPS_BARE_COMMAND: INSTALL_DEPS_LONG_OPTION,
        "start": "--start",
    }

    for token in raw_args:
        if expects_value_for is not None:
            normalized.append(token)
            expects_value_for = None
            continue

        if token in value_options and "=" not in token:
            normalized.append(token)
            expects_value_for = token
            continue

        if token.startswith("-"):
            normalized.append(token)
            continue

        bare_name, equals, value = token.partition("=")
        option = bare_to_option.get(bare_name)
        if option is None:
            normalized.append(token)
            continue

        if equals:
            normalized.append(f"{option}={value}")
            continue

        normalized.append(option)
        if option in value_options:
            expects_value_for = option

    return normalized


def build_argument_parser(program_name: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SoAI Main Application and Management Utility.",
        prog=program_name,
    )
    parser.add_argument(
        "-version",
        "--version",
        action="version",
        version=f"SoAI {__version__}",
        help="Print the SoAI backend version and exit.",
    )
    parser.add_argument(
        "-reset-user-password",
        "--reset-user-password",
        type=str,
        metavar="USERNAME",
        help="Run the password reset utility for the specified user and exit.",
    )
    parser.add_argument(
        "-start-no-browser",
        "--start-no-browser",
        action="store_true",
        help="Prevent automatic browser opening on startup.",
    )
    parser.add_argument(
        "-verbose",
        "--verbose",
        action="store_true",
        help="Enable verbose bootstrap logging output.",
    )
    parser.add_argument(
        "-restart",
        "--restart",
        action="store_true",
        help="Send a restart signal to the running SoAI instance and exit.",
    )
    parser.add_argument(
        "-stop",
        "--stop",
        action="store_true",
        help="Send a stop signal to the running SoAI instance and exit.",
    )
    parser.add_argument(
        "-status",
        "--status",
        action="store_true",
        help="Print the status of the running SoAI instance and exit.",
    )
    parser.add_argument(
        "-start",
        "--start",
        action="store_true",
        help="Start SoAI (same as running without flags, provided for symmetry).",
    )
    parser.add_argument(
        INSTALL_DEPS_SHORT_OPTION,
        INSTALL_DEPS_LONG_OPTION,
        action="store_true",
        help="Provision SoAI runtime dependencies and exit.",
    )
    return parser


def handle_information_cli_request(
    raw_args: list[str],
    *,
    program_name: str | None = None,
) -> int | None:
    normalized_args = normalize_cli_args(raw_args)
    if "-h" in normalized_args or "--help" in normalized_args:
        build_argument_parser(program_name=program_name).print_help()
        return 0
    if "-version" in normalized_args or "--version" in normalized_args:
        sys.stdout.write(f"SoAI {__version__}\n")
        return 0
    return None


def apply_environment_flags(args: argparse.Namespace) -> bool:
    if args.start_no_browser:
        os.environ["SOAI_NO_BROWSER"] = "1"
    bootstrap_verbose = os.environ.get("SOAI_BOOTSTRAP_VERBOSE", "") == "1"
    if args.verbose:
        os.environ["SOAI_BOOTSTRAP_VERBOSE"] = "1"
        bootstrap_verbose = True
    return bootstrap_verbose


def resolve_startup_action(parsed_args: argparse.Namespace) -> StartupAction:
    if parsed_args.install_deps:
        return "install_deps"
    if parsed_args.restart:
        return "restart"
    if parsed_args.stop:
        return "stop"
    if parsed_args.status:
        return "status"
    if parsed_args.reset_user_password:
        return "password_reset"
    return "start"
