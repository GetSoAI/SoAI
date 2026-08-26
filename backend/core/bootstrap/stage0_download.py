"""SoAI - Dependency-light stage-zero HTTPS downloads [backend/core/bootstrap/stage0_download.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import uuid

from core.errors.exceptions import StateError
from core.filesystem.open_files import create_binary_owner_only
from core.system.commands import run_argv_capture
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC

__all__ = ("download_https_file_atomic",)

STAGE0_DOWNLOAD_MAX_REDIRECTS = 5
STAGE0_DOWNLOAD_RETRY_COUNT = 4


def download_https_file_atomic(
    url: str,
    *,
    target_path: str,
    user_agent: str,
    timeout_sec: float,
    max_bytes: int,
) -> None:
    if not url.startswith("https://"):
        raise StateError("Stage-zero download URL must use HTTPS.")
    if max_bytes <= 0:
        raise StateError("Stage-zero download size limit must be positive.")
    target_directory = os.path.dirname(target_path)
    if target_directory:
        os.makedirs(target_directory, exist_ok=True)
    temp_path = f"{target_path}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
    try:
        with create_binary_owner_only(temp_path) as temp_handle:
            temp_handle.flush()
            os.fsync(temp_handle.fileno())
        executable = "curl.exe" if os.name == "nt" else "curl"
        result = run_argv_capture(
            [
                executable,
                "--fail",
                "--silent",
                "--show-error",
                "--location",
                "--proto",
                "=https",
                "--proto-redir",
                "=https",
                "--max-redirs",
                str(STAGE0_DOWNLOAD_MAX_REDIRECTS),
                "--retry",
                str(STAGE0_DOWNLOAD_RETRY_COUNT),
                "--retry-all-errors",
                "--retry-delay",
                str(RESPONSIVE_TIMEOUT_SEC),
                "--retry-max-time",
                str(max(1, int(timeout_sec))),
                "--max-filesize",
                str(max_bytes),
                "--user-agent",
                user_agent,
                "--output",
                temp_path,
                url,
            ],
            encoding="utf-8",
            errors="replace",
            timeout=max(1, int(timeout_sec)),
        )
        if result.return_code != 0:
            diagnostic = result.stderr.strip() or result.stdout.strip() or "no output"
            raise StateError(f"Stage-zero HTTPS download failed: {diagnostic}")
        downloaded_bytes = os.path.getsize(temp_path)
        if downloaded_bytes < 1 or downloaded_bytes > max_bytes:
            raise StateError("Stage-zero download size is invalid.")
        os.replace(temp_path, target_path)
    except OSError as exception:
        raise StateError(f"Stage-zero download failed for {url}.") from exception
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
