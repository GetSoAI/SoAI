"""SoAI - Plugin updater factories and update orchestration helpers [backend/plugins/state/updater.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx2

from core.config.protocols import ConfigProtocol
from core.plugins.protocols_guardian import UpdaterModuleDependenciesProtocol
from plugins.protocols_internal.runtime.internal_protocols import (
    FetchLatestSoAIReleaseAsyncProtocol,
)
from plugins.updater import Updater

if TYPE_CHECKING:
    type UpdaterFactory = Callable[
        [ConfigProtocol, httpx2.AsyncClient, UpdaterModuleDependenciesProtocol],
        Updater,
    ]

__all__ = ("build_updater_factory",)


def build_updater_factory(
    *,
    module_dependencies_type: type[UpdaterModuleDependenciesProtocol],
    fetch_latest_release_async: FetchLatestSoAIReleaseAsyncProtocol,
) -> UpdaterFactory:
    return functools.partial(
        Updater,
        module_dependencies_type=module_dependencies_type,
        fetch_latest_release_async=fetch_latest_release_async,
    )
