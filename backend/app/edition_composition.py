"""SoAI - Immutable edition composition contracts [backend/app/edition_composition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.composition.internal_protocols import HostManagementServiceBuilderProtocol
from app.internal_protocols import HostPersistenceProtocol, StagedUpdateValidationProtocol
from core.di.validation import require_dependencies
from core.licensing.policy import EditionLicensingPolicy

if TYPE_CHECKING:
    from core.licensing.types import Edition
    from core.mutations.edition_composition import DurableMutationComposition
    from core.tasks.command_routes import TaskCommandRoute
    from core.tasks.type_catalog import TaskTypeCatalog
    from features.api.runtime.container.route_composition import ApiRouteComposition

__all__ = (
    "EditionCapabilities",
    "EditionComposition",
    "HostManagementServiceComposition",
    "LifecycleComposition",
    "TaskComposition",
    "UpdaterComposition",
)


@dataclass(frozen=True, slots=True)
class EditionCapabilities:
    edition: Edition
    webui_relative_path: str
    webui_fallback_relative_paths: tuple[str, ...]
    host_management_available: bool
    host_management_enabled: bool


@dataclass(frozen=True, slots=True)
class HostManagementServiceComposition:
    build_services: HostManagementServiceBuilderProtocol | None


@dataclass(frozen=True, slots=True)
class TaskComposition:
    catalog: TaskTypeCatalog
    command_routes: tuple[TaskCommandRoute, ...]


@dataclass(frozen=True, slots=True)
class LifecycleComposition:
    ensure_host_persistence: HostPersistenceProtocol | None
    restart_cli_module: str


@dataclass(frozen=True, slots=True)
class UpdaterComposition:
    edition: str
    product_version: str
    core_version: str
    entrypoint_relative_path: str
    cli_module: str
    cli_relative_path: str
    post_update_hook_module: str
    post_update_hook_relative_path: str
    validate_staged_payload: StagedUpdateValidationProtocol

    def __post_init__(self) -> None:
        if self.edition not in {"soai-core", "soai-os"}:
            raise ValueError("Updater edition must be soai-core or soai-os.")
        if self.product_version != self.core_version:
            raise ValueError("SoAI product and Core versions must match.")
        for label, relative_path in (
            ("entrypoint", self.entrypoint_relative_path),
            ("CLI", self.cli_relative_path),
            ("post-update hook", self.post_update_hook_relative_path),
        ):
            if (
                not relative_path
                or relative_path.startswith(("/", "\\"))
                or "\\" in relative_path
                or ".." in relative_path.split("/")
            ):
                raise ValueError(f"Updater {label} path must be a safe relative path.")
        require_dependencies(
            owner="UpdaterComposition",
            cli_module=self.cli_module,
            cli_relative_path=self.cli_relative_path,
            entrypoint_relative_path=self.entrypoint_relative_path,
            post_update_hook_module=self.post_update_hook_module,
            post_update_hook_relative_path=self.post_update_hook_relative_path,
            validate_staged_payload=self.validate_staged_payload,
        )


@dataclass(frozen=True, slots=True)
class EditionComposition:
    capabilities: EditionCapabilities
    licensing: EditionLicensingPolicy
    host_management: HostManagementServiceComposition
    api_routes: ApiRouteComposition
    tasks: TaskComposition
    durable_mutations: DurableMutationComposition
    lifecycle: LifecycleComposition
    updater: UpdaterComposition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="EditionComposition",
            api_routes=self.api_routes,
            capabilities=self.capabilities,
            durable_mutations=self.durable_mutations,
            host_management=self.host_management,
            lifecycle=self.lifecycle,
            licensing=self.licensing,
            tasks=self.tasks,
            updater=self.updater,
        )
