"""SoAI - Managed runtime artifact bootstrap CLI [backend/core/bootstrap/runtime_artifacts_cli.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

from core.bootstrap.install_diagnostics import (
    configure_install_cancellation,
    read_install_diagnostics_context,
)
from core.bootstrap.runtime_artifacts import ensure_runtime_artifacts_if_needed

__all__ = ("main",)


def main() -> None:
    repo_root_path = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
    diagnostics = read_install_diagnostics_context()
    configure_install_cancellation(diagnostics)
    ensure_runtime_artifacts_if_needed(
        repo_root_path,
        python_executable=sys.executable,
        diagnostics=diagnostics,
    )


if __name__ == "__main__":
    main()
