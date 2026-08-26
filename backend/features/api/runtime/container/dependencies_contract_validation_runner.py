"""SoAI - API runtime container contract validation [backend/features/api/runtime/container/dependencies_contract_validation_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.protocols import ConfigProtocol
from core.files.protocols import FilesPathResolverProtocol
from features.api.runtime.container import dependencies_contract_validation

__all__ = ("validate_api_dependencies_contract",)


def validate_api_dependencies_contract(
    *,
    base_dir: str,
    main_venv_dir: str,
    config: ConfigProtocol,
    files: FilesPathResolverProtocol,
) -> None:
    dependencies_contract_validation.validate_api_dependency_paths(
        base_dir=base_dir,
        main_venv_dir=main_venv_dir,
    )
    dependencies_contract_validation.validate_api_dependencies_contract(config=config, files=files)
