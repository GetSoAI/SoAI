"""SoAI - Plugin worker baseline requirement selection [backend/plugins/environments/baseline.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from core.errors.exceptions import StateError
from core.filesystem.open_files import open_text
from core.meta.paths import get_repo_root

__all__ = (
    "read_plugin_worker_baseline_package_names",
    "read_plugin_worker_baseline_requirements",
)

WORKER_BASELINE_PACKAGE_NAMES_RAW: tuple[str, ...] = (
    "dnspython",
    "httpx2",
    "psutil",
    "pydantic",
    "typing-extensions",
    "zstandard",
)


def read_plugin_worker_baseline_package_names() -> tuple[str, ...]:
    return tuple(str(canonicalize_name(name)) for name in WORKER_BASELINE_PACKAGE_NAMES_RAW)


def read_plugin_worker_baseline_requirements() -> tuple[str, ...]:
    requirements_path = os.path.join(get_repo_root(), "requirements.txt")
    baseline_names = read_plugin_worker_baseline_package_names()
    selected: dict[str, str] = {}
    with open_text(requirements_path, encoding="utf-8") as handle:
        for line in handle:
            requirement = _parse_requirement_line(line)
            if requirement is None:
                continue
            name = str(canonicalize_name(requirement.name))
            if name in baseline_names:
                selected[name] = str(requirement)
    missing = [name for name in baseline_names if name not in selected]
    if missing:
        raise StateError(
            "Plugin worker baseline requirements are missing.",
            details={"missing": missing},
        )
    return tuple(selected[name] for name in baseline_names)


def _parse_requirement_line(line: str) -> Requirement | None:
    candidate = line.strip()
    if (
        not candidate
        or candidate.startswith("#")
        or candidate.startswith("--")
        or candidate.startswith("./")
    ):
        return None
    try:
        return Requirement(candidate)
    except InvalidRequirement as exception:
        raise StateError(
            "Invalid runtime requirement while selecting plugin worker baseline.",
            details={"requirement": candidate},
        ) from exception
