"""SoAI - Standalone main application updater CLI [backend/app/updater/cli.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import argparse

from app.cli.offline_mode import resolve_config_path
from app.core_edition import build_core_edition_composition
from app.dependencies import build_updater_module_dependencies
from app.edition_composition import EditionComposition
from app.updater.errors import parse_updater_args
from app.updater.service import Updater, UpdaterDependencies
from core.meta.paths import get_repo_root

__all__ = ("main",)


def main(edition_composition: EditionComposition) -> None:
    parser = argparse.ArgumentParser(
        description="SoAI Updater: A tool to check for and apply updates to the SoAI application and its plugins.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--update-software",
        action="store_true",
        help="Update the main SoAI application (default action).",
    )
    action_group.add_argument(
        "--update-plugins",
        action="store_true",
        help="Check for and install updates for plugins.",
    )
    action_group.add_argument(
        "--check-update-software",
        action="store_true",
        help="Check for new SoAI software versions without installing.",
    )
    action_group.add_argument(
        "--check-update-plugins",
        action="store_true",
        help="Check for new plugin versions without installing.",
    )
    action_group.add_argument(
        "--check-update-venv",
        action="store_true",
        help="Check for updates to the SoAI core virtual environment.",
    )
    plugin_group = parser.add_argument_group("Plugin/API Options")
    plugin_group.add_argument("--port", type=int, help="Manually specify the SoAI API port.")
    plugin_group.add_argument(
        "--username",
        type=str,
        help="Authenticate protected updater API calls with this WebUI username.",
    )
    plugin_group.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the WebUI password for --username from stdin.",
    )
    general_group = parser.add_argument_group("General Options")
    general_group.add_argument(
        "--config",
        default=resolve_config_path(get_repo_root()),
        help="Path to the SoAI config.yaml file.",
    )
    general_group.add_argument(
        "--silent",
        action="store_true",
        help="Run update processes without user prompts.",
    )
    general_group.add_argument(
        "--no-restart",
        action="store_true",
        help="Do not restart SoAI automatically after updating software.",
    )
    general_group.add_argument("--debug", action="store_true", help="Enable debug level logging.")
    internal_group = parser.add_argument_group("Internal Options")
    internal_group.add_argument("--wait-for-pid", type=int, help=argparse.SUPPRESS)
    internal_group.add_argument("--task-id", help=argparse.SUPPRESS)
    args = parser.parse_args()
    primary_flags = (
        args.update_software,
        args.update_plugins,
        args.check_update_software,
        args.check_update_plugins,
        args.check_update_venv,
    )
    if not any(primary_flags):
        args.update_software = True
    module_dependencies = build_updater_module_dependencies()
    raise SystemExit(
        Updater(
            UpdaterDependencies(
                args=parse_updater_args(args),
                module_dependencies=module_dependencies,
                updater=edition_composition.updater,
            ),
        ).run(),
    )


if __name__ == "__main__":
    main(build_core_edition_composition())
