"""SoAI - Stage-zero production entrypoint [backend/main.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

from app.cli.startup_flags import handle_information_cli_request
from core.bootstrap.launch_console import emit
from core.bootstrap.stage0_application import run_stage0_application
from core.edition.preflight import require_core_edition_request
from core.errors.exceptions import EditionUnavailableError

__all__ = ()


def _main() -> int:
    try:
        require_core_edition_request(sys.argv[1:])
    except EditionUnavailableError as exception:
        emit("ERROR", f"Startup configuration error: {exception}")
        return 2
    information_exit_code = handle_information_cli_request(
        sys.argv[1:],
        program_name=os.path.basename(sys.argv[0]),
    )
    if information_exit_code is not None:
        return information_exit_code
    return run_stage0_application(
        bootstrap_module="app.bootstrap_entrypoint",
        entrypoint_path=__file__,
    )


if __name__ == "__main__":
    raise SystemExit(_main())
