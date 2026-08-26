"""SoAI - Password reset CLI handoff entrypoint [backend/app/cli/password_reset_entrypoint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import argparse

from app.cli.password_reset import run_password_reset
from core.meta.paths import get_repo_root
from core.tasks.type_catalog import build_base_task_catalog

__all__ = ("main",)


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SoAI admin password reset.")
    parser.add_argument("--username", required=True)
    parsed_args = parser.parse_args(arguments)
    run_password_reset(
        str(parsed_args.username),
        base_dir=get_repo_root(),
        task_catalog=build_base_task_catalog(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
