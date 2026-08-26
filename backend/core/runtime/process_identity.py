"""SoAI - Runtime process identity markers [backend/core/runtime/process_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Sequence

__all__ = (
    "SOAI_BACKEND_MAIN_SUBPATH",
    "is_management_process_command",
    "is_soai_instance_process",
    "is_soai_owned_process_markers",
    "is_soai_process_command",
)

SOAI_BACKEND_MAIN_SUBPATH = "backend/main.py"
_MANAGEMENT_COMMAND_TOKENS = frozenset(
    {
        "--restart",
        "-restart",
        "restart",
        "--stop",
        "-stop",
        "stop",
        "--status",
        "-status",
        "status",
        "--reset-user-password",
        "-reset-user-password",
        "reset-user-password",
    },
)
_MANAGEMENT_COMMAND_PREFIXES = (
    "--reset-user-password=",
    "-reset-user-password=",
)


def is_soai_process_command(command_parts: Sequence[str]) -> bool:
    normalized_parts = [str(part).lower().replace("\\", "/") for part in command_parts]
    if any(
        part.endswith("app.cli.entrypoint") or part == "app.cli.entrypoint"
        for part in normalized_parts
    ):
        return True
    if any(part.endswith("backend.main") or part == "backend.main" for part in normalized_parts):
        return True
    if any(part.endswith(SOAI_BACKEND_MAIN_SUBPATH) for part in normalized_parts):
        return True
    return any(
        part.endswith("/backend/main.py") or part == "backend/main.py" for part in normalized_parts
    )


def is_management_process_command(command_parts: Sequence[str]) -> bool:
    for part in command_parts:
        token = str(part).lower()
        if token in _MANAGEMENT_COMMAND_TOKENS:
            return True
        if token.startswith(_MANAGEMENT_COMMAND_PREFIXES):
            return True
    return False


def is_soai_owned_process_markers(markers: Sequence[str], *, base_dir: str) -> bool:
    normalized_base = os.path.realpath(base_dir)
    base_with_separator = f"{normalized_base}{os.sep}"
    for marker in markers:
        value = os.path.realpath(marker) if marker else ""
        if value == normalized_base or value.startswith(base_with_separator):
            return True
        assignment_marker = f"={normalized_base}"
        if marker.endswith(assignment_marker):
            return True
        if f"{assignment_marker}{os.pathsep}" in marker:
            return True
        if f"{assignment_marker}{os.sep}" in marker:
            return True
    return False


def is_soai_instance_process(
    command_parts: Sequence[str],
    *,
    markers: Sequence[str],
    base_dir: str,
) -> bool:
    if is_management_process_command(command_parts):
        return False
    if not is_soai_owned_process_markers(markers, base_dir=base_dir):
        return False
    return is_soai_process_command(command_parts)
