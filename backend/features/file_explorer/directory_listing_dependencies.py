"""SoAI - Directory listing service dependencies [backend/features/file_explorer/directory_listing_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.concurrency.path_tree_lock import AsyncPathTreeLock
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.files.protocols import FilesPathResolverProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskRegistryProtocol,
)
from features.file_explorer.internal_protocols import (
    DirectoryListingBuilderProtocol,
    DirectoryListingRegistryProtocol,
)

__all__ = (
    "DirectoryListingBuilderDependencies",
    "DirectoryListingManagerDependencies",
    "DirectoryListingRegistryDependencies",
)


@dataclass(frozen=True, slots=True)
class DirectoryListingRegistryDependencies:
    monotonic_clock: Callable[[], int]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DirectoryListingRegistryDependencies",
            monotonic_clock=self.monotonic_clock,
        )


@dataclass(frozen=True, slots=True)
class DirectoryListingManagerDependencies:
    builder: DirectoryListingBuilderProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    registry: DirectoryListingRegistryProtocol
    task_registry: TaskRegistryProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DirectoryListingManagerDependencies",
            builder=self.builder,
            cancellation_binder=self.cancellation_binder,
            registry=self.registry,
            task_registry=self.task_registry,
        )


@dataclass(frozen=True, slots=True)
class DirectoryListingBuilderDependencies:
    config: ConfigProtocol
    files: FilesPathResolverProtocol
    mutation_locks: AsyncPathTreeLock
    registry: DirectoryListingRegistryProtocol
    task_registry: TaskRegistryProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DirectoryListingBuilderDependencies",
            config=self.config,
            files=self.files,
            mutation_locks=self.mutation_locks,
            registry=self.registry,
            task_registry=self.task_registry,
        )
