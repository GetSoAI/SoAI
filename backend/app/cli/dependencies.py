"""SoAI - CLI dependency injection bundles [backend/app/cli/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from app.internal_protocols import InstanceLockProtocol

__all__ = ("ApplicationDependencies",)


@dataclass(frozen=True, slots=True)
class ApplicationDependencies:
    base_dir: str
    config_path: str
    venv_path: str
    version: str
    pid_lock: InstanceLockProtocol | None
    bootstrap_logger: logging.Logger
    lifecycle_logger: logging.Logger

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationDependencies",
            base_dir=self.base_dir,
            bootstrap_logger=self.bootstrap_logger,
            config_path=self.config_path,
            lifecycle_logger=self.lifecycle_logger,
            venv_path=self.venv_path,
            version=self.version,
        )
