"""SoAI - WebUI notifications REST routes [backend/features/api/routes/webui/notifications_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Query, Request, Response

from core.notifications.notification_record_models import (
    NotificationRecord,
    NotificationsListRequest,
    NotificationsListResponse,
    NotificationsMarkReadRequest,
)
from core.notifications.notification_source_visibility import (
    resolve_notification_excluded_sources,
)
from core.state.access import AccessAction
from features.api.middleware.acl_enforcement import request_has_action
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_not_found
from features.api.runtime.responses import create_no_content_response
from features.api.runtime.webui_records import webui_require_true_or_404

__all__ = ("register_routes",)


async def _resolve_excluded_notification_sources(request: Request) -> frozenset[str]:
    return resolve_notification_excluded_sources(
        can_read_plugins=await request_has_action(request, AccessAction.PLUGIN_READ),
    )


def register_routes(routers: ApiRouters) -> None:
    router = routers.webui
    notifications_deps = require_action_dependencies(AccessAction.NOTIFICATIONS)

    @router.get(
        "/notifications",
        response_model=NotificationsListResponse,
        dependencies=notifications_deps,
    )
    async def list_notifications(
        request: Request,
        limit: int = Query(default=100, ge=1, le=500),
        before_created_at_ms: int | None = Query(default=None, ge=1),
        before_id: str | None = Query(default=None, min_length=1),
        unread_only: bool = Query(default=False),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> NotificationsListResponse:
        database_notifications = api_context.dependencies.database_notifications
        excluded_sources = await _resolve_excluded_notification_sources(request)
        list_request = NotificationsListRequest(
            limit=int(limit),
            before_created_at_ms=before_created_at_ms,
            before_id=before_id,
            unread_only=bool(unread_only),
        )
        notifications_page = await database_notifications.list_notifications(
            current_user["id"],
            limit=list_request.limit,
            before_created_at_ms=list_request.before_created_at_ms,
            before_id=list_request.before_id,
            unread_only=list_request.unread_only,
            excluded_sources=excluded_sources,
        )
        total_count, unread_count = await database_notifications.get_notification_counts(
            current_user["id"],
            excluded_sources=excluded_sources,
        )
        return NotificationsListResponse(
            notifications=notifications_page.notifications,
            total_count=int(total_count),
            unread_count=int(unread_count),
            next_cursor=notifications_page.next_cursor,
        )

    @router.post("/notifications/mark-read", status_code=204, dependencies=notifications_deps)
    async def mark_notifications_read(
        _request: Request,
        payload: NotificationsMarkReadRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        database_notifications = api_context.dependencies.database_notifications
        await database_notifications.mark_notifications_read(
            current_user["id"],
            notification_ids=payload.notification_ids,
        )
        return create_no_content_response()

    @router.post(
        "/notifications/{notification_id}/open",
        response_model=NotificationRecord,
        dependencies=notifications_deps,
    )
    async def open_notification(
        request: Request,
        notification_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> NotificationRecord:
        database_notifications = api_context.dependencies.database_notifications
        excluded_sources = await _resolve_excluded_notification_sources(request)
        normalized_id = str(notification_id or "").strip()
        notification = await database_notifications.open_notification(
            current_user["id"],
            notification_id=normalized_id,
            excluded_sources=excluded_sources,
        )
        if notification is None:
            raise_not_found(request, "Notification not found.")
        return notification

    @router.delete(
        "/notifications/{notification_id}",
        status_code=204,
        dependencies=notifications_deps,
    )
    async def delete_notification(
        request: Request,
        notification_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        database_notifications = api_context.dependencies.database_notifications
        normalized_id = str(notification_id or "").strip()
        await webui_require_true_or_404(
            request,
            database_notifications.delete_notification(
                current_user["id"],
                notification_id=normalized_id,
            ),
            message="Notification not found.",
        )
        return create_no_content_response()

    @router.delete("/notifications", status_code=204, dependencies=notifications_deps)
    async def clear_notifications(
        _request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        database_notifications = api_context.dependencies.database_notifications
        await database_notifications.clear_notifications(current_user["id"])
        return create_no_content_response()
