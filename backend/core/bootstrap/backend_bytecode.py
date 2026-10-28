"""SoAI - Install-time backend bytecode compilation [backend/core/bootstrap/backend_bytecode.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Callable

from core.bootstrap.venv_paths import get_venv_path, get_venv_python_executable
from core.errors.exceptions import StateError
from core.system.commands import run_argv_capture

__all__ = ("BACKEND_BYTECODE_TIMEOUT_SEC", "compile_backend_bytecode")

BACKEND_BYTECODE_TIMEOUT_SEC = 900


def compile_backend_bytecode(
    repo_root_path: str, *, progress: Callable[[str], None] | None = None
) -> None:
    root = os.path.abspath(repo_root_path)
    backend = os.path.join(root, "backend")
    python_executable = get_venv_python_executable(get_venv_path(root))
    if not os.path.isfile(python_executable):
        raise StateError(
            "The managed Python runtime is missing; backend bytecode cannot be prepared.",
            details={"python_executable": python_executable},
        )
    entries = sorted(entry for entry in os.listdir(backend) if entry != "__pycache__")
    packages = [entry for entry in entries if os.path.isdir(os.path.join(backend, entry))]
    modules = [entry for entry in entries if entry.endswith(".py")]
    batches = [[package] for package in packages] + ([modules] if modules else [])
    for batch in batches:
        result = run_argv_capture(
            [
                python_executable,
                "-m",
                "compileall",
                "-q",
                "-j",
                "0",
                *(os.path.join(backend, entry) for entry in batch),
            ],
            timeout=BACKEND_BYTECODE_TIMEOUT_SEC,
            cwd=root,
        )
        if result.return_code != 0:
            raise StateError(
                "SoAI backend bytecode preparation failed.",
                details={
                    "entries": batch,
                    "return_code": result.return_code,
                    "output": (result.stdout + result.stderr).strip()[-2000:],
                },
            )
        if progress is not None:
            progress(", ".join(batch))
