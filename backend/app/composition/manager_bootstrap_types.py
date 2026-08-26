"""SoAI - Manager services bootstrap component types [backend/app/composition/manager_bootstrap_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.concurrency.lock_registry import TTLAsyncLockRegistry
    from models.actions.purge_records import ModelDatabasePurgeService
    from models.manager.registry import ModelRegistry
    from models.parameters.manager import ParameterManager
    from models.providers.coordinator import ModelProviderCoordinator

    type ModelBootstrapComponents = tuple[
        ParameterManager,
        ModelDatabasePurgeService,
        ModelRegistry,
        ModelProviderCoordinator,
        TTLAsyncLockRegistry[str],
    ]

__all__ = ()
