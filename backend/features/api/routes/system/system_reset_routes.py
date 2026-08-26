"""SoAI - System destructive reset routes [backend/features/api/routes/system/system_reset_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import stat
from typing import Literal

from fastapi import BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field

from core.files.managed_path_access import stat_managed_path
from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.path_policy import is_path_within_base
from core.hardware.reservation_claims import claim_reserved_write
from core.meta.paths import join_data_abs
from core.restart_purge.transaction import (
    create_restart_purge_transaction,
    restart_purge_transaction_required_bytes,
)
from core.state.access import AccessAction
from features.api.routes.system.factory_reset_manifest import (
    collect_factory_reset_manifest,
)
from features.api.runtime.access_dependencies import restart_protected_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_forbidden, raise_precondition_failed

__all__ = (
    "FactoryResetInitiatedResponse",
    "configuration_reset_system",
    "factory_reset_system",
    "register_routes",
)


class FactoryResetInitiatedResponse(BaseModel):
    message: str = Field(min_length=1)
    purged_paths_manifest: list[str]


class ConfigurationResetAcceptedResponse(BaseModel):
    status: Literal["accepted"]
    message: str = Field(min_length=1)


async def configuration_reset_system(
    request: Request,
    background_tasks: BackgroundTasks,
    api_context: ApiContext = Depends(resolve_api_context),
) -> ConfigurationResetAcceptedResponse:
    base_dir = os.path.realpath(api_context.dependencies.base_dir)
    active_config_path = api_context.dependencies.config_manager.get_config_path_sync("core")
    canonical_default_path = join_data_abs(base_dir, "config", "config.default.yaml")
    _require_managed_regular_file(request, base_dir, active_config_path)
    _require_managed_regular_file(request, base_dir, canonical_default_path)
    targets = (
        active_config_path,
        f"{active_config_path}.backup",
        f"{active_config_path}.base_path_correction.backup",
    )
    await _publish_restart_purge(
        request=request,
        background_tasks=background_tasks,
        api_context=api_context,
        base_dir=base_dir,
        paths_to_delete=targets,
        operation="system.configuration_reset.write_transaction",
    )
    log_audit_event(request, "RESET_CONFIGURATION", "core_configuration")
    return ConfigurationResetAcceptedResponse(
        status="accepted",
        message="Configuration reset accepted. The application will now restart.",
    )


async def factory_reset_system(
    request: Request,
    background_tasks: BackgroundTasks,
    api_context: ApiContext = Depends(resolve_api_context),
) -> FactoryResetInitiatedResponse:
    base_dir = os.path.realpath(api_context.dependencies.base_dir)
    targets = await collect_factory_reset_manifest(
        request=request,
        api_context=api_context,
        base_dir=base_dir,
    )
    await _publish_restart_purge(
        request=request,
        background_tasks=background_tasks,
        api_context=api_context,
        base_dir=base_dir,
        paths_to_delete=targets,
        operation="system.factory_reset.write_transaction",
    )
    log_audit_event(request, "FACTORY_RESET_INITIATED", "all_system_data")
    return FactoryResetInitiatedResponse(
        message=(
            "Factory reset initiated. The application will now shut down to perform data "
            "purge and will restart in a clean state."
        ),
        purged_paths_manifest=list(targets),
    )


async def _publish_restart_purge(
    *,
    request: Request,
    background_tasks: BackgroundTasks,
    api_context: ApiContext,
    base_dir: str,
    paths_to_delete: tuple[str, ...],
    operation: str,
) -> None:
    _raise_if_reset_disabled(request, api_context)
    manifest_path = os.path.join(base_dir, "restart_purge.manifest.json")
    sentinel_path = os.path.join(base_dir, "restart_purge.sentinel")
    required_bytes = restart_purge_transaction_required_bytes(paths_to_delete)
    with api_context.dependencies.storage_manager.reserve_disk_space(
        path=manifest_path,
        required_bytes=required_bytes,
        operation=operation,
        details={"required_bytes": required_bytes},
    ) as reservation:
        with claim_reserved_write(reservation, size_bytes=required_bytes):
            _raise_if_reset_disabled(request, api_context)
            await asyncio.to_thread(
                create_restart_purge_transaction,
                sentinel_path=sentinel_path,
                manifest_path=manifest_path,
                paths_to_delete=paths_to_delete,
            )
    background_tasks.add_task(api_context.dependencies.application_control.restart)


def _require_managed_regular_file(request: Request, base_dir: str, path: str) -> None:
    if not is_path_within_base(base_dir, path):
        raise_precondition_failed(
            request,
            "Configuration reset requires application-managed configuration files.",
            error_type="configuration_reset_precondition_failed",
        )
    try:
        file_status = stat_managed_path(base_dir, path)
    except (FileStorageSecurityError, OSError):
        raise_precondition_failed(
            request,
            "Configuration reset requires valid regular configuration files.",
            error_type="configuration_reset_precondition_failed",
        )
    if not stat.S_ISREG(file_status.st_mode):
        raise_precondition_failed(
            request,
            "Configuration reset requires valid regular configuration files.",
            error_type="configuration_reset_precondition_failed",
        )


def _raise_if_reset_disabled(request: Request, api_context: ApiContext) -> None:
    if api_context.dependencies.runtime_flags.host_system_actions_disabled:
        raise_forbidden(
            request,
            "Reset is disabled because host system actions are disabled.",
            error_type="action_not_supported",
        )


def register_routes(routers: ApiRouters) -> None:
    routers.system.post(
        "/admin/configuration/reset",
        status_code=202,
        response_model=ConfigurationResetAcceptedResponse,
        dependencies=restart_protected_dependencies(AccessAction.CONFIG_PATCH),
    )(configuration_reset_system)
    routers.system.post(
        "/admin/factory-reset",
        status_code=202,
        response_model=FactoryResetInitiatedResponse,
        dependencies=restart_protected_dependencies(AccessAction.FACTORY_RESET),
    )(factory_reset_system)
