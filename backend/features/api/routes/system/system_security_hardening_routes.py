"""SoAI - Security hardening audit routes [backend/features/api/routes/system/system_security_hardening_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.config.runtime_config import Config
from core.config.value_validation import is_config_dict
from core.errors.exceptions import StateError
from core.security.hardening_collection import (
    SecurityHardeningCollectionDependencies,
    collect_complete_security_hardening_issues,
)
from core.security.hardening_report import build_security_hardening_report
from core.serialization.json import normalize_for_json
from core.state.access import AccessAction
from core.types.json import JSONDict
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

__all__ = ("register_routes",)


async def _load_persisted_core_config(api_context: ApiContext) -> Config:
    raw_config = await api_context.dependencies.config_manager.load_config(
        "core",
        force_reload=True,
    )
    normalized_config = normalize_for_json(raw_config) if raw_config is not None else None
    if not is_config_dict(normalized_config):
        raise StateError("Persisted core configuration is not config-compatible.")
    return Config(
        normalized_config,
        main_app_base_dir=api_context.dependencies.base_dir,
    )


async def _collect_security_hardening_report(api_context: ApiContext) -> JSONDict:
    config = await _load_persisted_core_config(api_context)
    hardening_deps = SecurityHardeningCollectionDependencies(
        base_dir=api_context.dependencies.base_dir,
        files=api_context.dependencies.files,
        database_users=api_context.dependencies.database_users,
        database_tokens=api_context.dependencies.database_tokens,
        database_api_keys=api_context.dependencies.database_api_keys,
        database_mcp_access_tokens=(
            api_context.dependencies.webui_manager.database_mcp_access_tokens
        ),
    )
    issues = await collect_complete_security_hardening_issues(
        config,
        hardening_deps,
    )
    return build_security_hardening_report(issues)


def register_routes(routers: ApiRouters) -> None:
    @routers.system.get(
        "/security/hardening",
        dependencies=require_action_dependencies(
            AccessAction.ACL_ADMIN,
            AccessAction.CONFIG_PATCH,
        ),
    )
    async def get_security_hardening_audit(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return JSONResponse(content=await _collect_security_hardening_report(api_context))
