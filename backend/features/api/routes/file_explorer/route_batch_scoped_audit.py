"""SoAI - File explorer batch-scoped route helpers [backend/features/api/routes/file_explorer/route_batch_scoped_audit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.file_explorer.route_scope_context import (
    require_file_explorer_batch_scoped,
)
from features.api.runtime.audit import log_audit_event

if TYPE_CHECKING:
    from fastapi import Request

    from core.types.json import JSONValue
    from features.api.routes.file_explorer.route_scope_context import (
        FileExplorerBatchScopeContext,
    )
    from features.api.runtime.context import ApiContext
    from features.api.runtime.current_user import CurrentUser

__all__ = ("require_file_explorer_batch_scoped_with_audit",)


def require_file_explorer_batch_scoped_with_audit(
    request: Request,
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
    audit_event: str,
    audit_details: dict[str, JSONValue],
) -> FileExplorerBatchScopeContext:
    log_audit_event(request, audit_event, "file_explorer", details=dict(audit_details))
    return require_file_explorer_batch_scoped(
        request,
        api_context=api_context,
        current_user=current_user,
    )
