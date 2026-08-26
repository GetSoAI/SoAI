"""SoAI - Bootstrap console output helpers [backend/core/bootstrap/launch_console.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys
from datetime import UTC, datetime

__all__ = (
    "emit",
    "now_timestamp",
)


def now_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit(level: str, message: str) -> None:
    sys.stderr.write(f"{now_timestamp()} - [SoAI/Launcher] - {level} - {message}\n")
    sys.stderr.flush()
