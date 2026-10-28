"""SoAI - Verified managed Python environment fingerprint [backend/core/bootstrap/dependency_verification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os

from core.bootstrap.files import read_text_file, write_text_file_atomic
from core.bootstrap.launch_console import emit
from core.bootstrap.venv_markers import VERIFIED_ENVIRONMENT_MARKER_FILENAME
from core.bootstrap.venv_paths import get_venv_site_package_paths

__all__ = ("record_verified_environment", "verified_environment_is_current")


def _environment_fingerprint(venv_path: str, requirements_hash: str) -> str:
    digest = hashlib.sha256(requirements_hash.encode("utf-8"))
    for site_packages in get_venv_site_package_paths(venv_path):
        names = sorted(name for name in os.listdir(site_packages) if name != "__pycache__")
        digest.update(b"\1")
        digest.update("\0".join(names).encode("utf-8"))
    return digest.hexdigest()


def verified_environment_is_current(venv_path: str, requirements_hash: str) -> bool:
    try:
        fingerprint = _environment_fingerprint(venv_path, requirements_hash)
    except OSError as exception:
        emit(
            "WARNING",
            f"Managed Python environment verification cache is unavailable ({exception.strerror or type(exception).__name__}); dependency probes will run.",
        )
    else:
        marker = read_text_file(os.path.join(venv_path, VERIFIED_ENVIRONMENT_MARKER_FILENAME))
        return marker == fingerprint
    return False


def record_verified_environment(venv_path: str, requirements_hash: str) -> None:
    try:
        fingerprint = _environment_fingerprint(venv_path, requirements_hash)
        write_text_file_atomic(
            os.path.join(venv_path, VERIFIED_ENVIRONMENT_MARKER_FILENAME), fingerprint
        )
    except OSError as exception:
        emit(
            "WARNING",
            f"Managed Python environment verification cache could not be recorded ({exception.strerror or type(exception).__name__}); the next start will recheck it.",
        )
