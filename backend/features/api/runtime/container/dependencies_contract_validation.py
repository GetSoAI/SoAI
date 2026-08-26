"""SoAI - API dependency contract validation helpers [backend/features/api/runtime/container/dependencies_contract_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.files.protocols import FilesPathResolverProtocol

__all__ = (
    "validate_api_dependencies_contract",
    "validate_api_dependency_paths",
)


def validate_api_dependencies_contract(
    *,
    config: ConfigProtocol,
    files: FilesPathResolverProtocol,
) -> None:
    try:
        config_get = config.get
    except AttributeError:
        config_get = None
    if not callable(config_get):
        raise ValidationError(
            "ApiDependencies.config must provide a callable get() method.",
            details={"actual_type": type(config).__name__},
        )
    try:
        resolve_path = files.resolve_path
    except AttributeError:
        resolve_path = None
    if not callable(resolve_path):
        raise ValidationError(
            "ApiDependencies.files must provide a callable resolve_path() method.",
            details={"actual_type": type(files).__name__},
        )


def validate_api_dependency_paths(*, base_dir: str, main_venv_dir: str) -> None:
    missing: list[str] = []
    if not base_dir:
        missing.append("base_dir")
    if not main_venv_dir:
        missing.append("main_venv_dir")
    if missing:
        raise ValidationError("ApiDependencies missing deps.", details={"missing": missing})
