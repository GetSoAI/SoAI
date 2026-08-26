"""SoAI - Race-safe admin notification alert creation [backend/database/repositories/users/notification_admin_alerts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid

from core.errors.exceptions import StateError
from core.notifications.notification_contracts import (
    NOTIFICATION_TYPE_SQL_VALUES,
    NotificationTemplateId,
)
from core.notifications.notification_text_models import (
    notification_text_from_template,
    serialize_notification_text_db,
)
from database.core.query_execution import (
    sync_fetch_all_as_dicts,
    sync_fetch_one_as_dict,
)
from database.core.sqlite_numbers import (
    coerce_required_int_from_sqlite_row,
)
from database.repositories.users.notifications_sync_creation import (
    sync_create_notification,
)

__all__ = ("sync_create_template_admin_alert_if_due",)


def _require_alert_string(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise StateError(f"{label} is invalid.")
    normalized = value.strip()
    if not normalized:
        raise StateError(f"{label} is invalid.")
    return normalized


def _validate_alert_inputs(now_ms: int, cooldown_ms: int, max_per_user: int) -> None:
    if (not isinstance(now_ms, int)) or isinstance(now_ms, bool) or now_ms <= 0:
        raise StateError("Notification alert now_ms is invalid.")
    if (not isinstance(cooldown_ms, int)) or isinstance(cooldown_ms, bool) or cooldown_ms <= 0:
        raise StateError("Notification alert cooldown_ms is invalid.")
    if (not isinstance(max_per_user, int)) or isinstance(max_per_user, bool) or max_per_user <= 0:
        raise StateError("Notification alert max_per_user is invalid.")


def _sync_resolve_alert_count(
    conn: sqlite3.Connection, alert_id: str, now_ms: int, cooldown_ms: int
) -> int:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT last_emitted_at_ms, pending_count
            FROM webui_notification_alert_state
            WHERE alert_id = ?
            """,
            (alert_id,),
        ),
    )
    if row is None:
        conn.execute(
            """
            INSERT INTO webui_notification_alert_state (
                alert_id, last_emitted_at_ms, pending_count, updated_at_ms
            ) VALUES (?, ?, 0, ?)
            """,
            (alert_id, int(now_ms), int(now_ms)),
        )
        return 1
    last_emitted_at_ms = coerce_required_int_from_sqlite_row(row, "last_emitted_at_ms")
    pending_count = coerce_required_int_from_sqlite_row(row, "pending_count")
    if last_emitted_at_ms <= 0 or pending_count < 0:
        raise StateError("Notification alert state is invalid.")
    if int(now_ms) < (int(last_emitted_at_ms) + int(cooldown_ms)):
        conn.execute(
            """
            UPDATE webui_notification_alert_state
            SET pending_count = pending_count + 1,
                updated_at_ms = ?
            WHERE alert_id = ?
            """,
            (int(now_ms), alert_id),
        )
        return 0
    alert_count = int(pending_count) + 1
    conn.execute(
        """
        UPDATE webui_notification_alert_state
        SET last_emitted_at_ms = ?,
            pending_count = 0,
            updated_at_ms = ?
        WHERE alert_id = ?
        """,
        (int(now_ms), int(now_ms), alert_id),
    )
    return alert_count


def _sync_list_admin_user_ids(conn: sqlite3.Connection) -> list[int]:
    rows = sync_fetch_all_as_dicts(conn.execute("""
            SELECT id
            FROM webui_users
            WHERE account_type = 'human' AND is_admin = 1
            ORDER BY id ASC
            """))
    return [coerce_required_int_from_sqlite_row(row, "id") for row in rows]


def _build_template_text(
    template_value: str,
    params: dict[str, str],
) -> str:
    return serialize_notification_text_db(
        notification_text_from_template(
            NotificationTemplateId(template_value),
            dict(params),
        ),
    )


def _build_message_params(
    base_params: dict[str, str],
    aggregate_param_name: str | None,
    alert_count: int,
) -> dict[str, str]:
    params = dict(base_params)
    if aggregate_param_name is not None:
        params[aggregate_param_name] = str(int(alert_count))
    return params


def sync_create_template_admin_alert_if_due(
    conn: sqlite3.Connection,
    alert_id: str,
    type_value: str,
    title_template_value: str,
    title_params: dict[str, str],
    message_template_value: str,
    message_params: dict[str, str],
    aggregate_param_name: str | None,
    source: str | None,
    now_ms: int,
    cooldown_ms: int,
    max_per_user: int,
) -> int:
    normalized_alert_id = _require_alert_string(alert_id, "Notification alert_id")
    if type_value not in NOTIFICATION_TYPE_SQL_VALUES:
        raise StateError("Notification alert type is invalid.")
    normalized_aggregate_param_name = aggregate_param_name
    if aggregate_param_name is not None:
        normalized_aggregate_param_name = _require_alert_string(
            aggregate_param_name, "Notification aggregate param"
        )
    normalized_source = source
    if source is not None:
        normalized_source = _require_alert_string(source, "Notification source")
    _validate_alert_inputs(now_ms, cooldown_ms, max_per_user)
    admin_user_ids = _sync_list_admin_user_ids(conn)
    if not admin_user_ids:
        return 0
    title = _build_template_text(title_template_value, title_params)
    validation_message = _build_template_text(
        message_template_value,
        _build_message_params(message_params, normalized_aggregate_param_name, 1),
    )
    alert_count = _sync_resolve_alert_count(
        conn, normalized_alert_id, int(now_ms), int(cooldown_ms)
    )
    if alert_count <= 0:
        return 0
    message = (
        validation_message
        if normalized_aggregate_param_name is None
        else _build_template_text(
            message_template_value,
            _build_message_params(message_params, normalized_aggregate_param_name, alert_count),
        )
    )
    created_count = 0
    for admin_user_id in admin_user_ids:
        sync_create_notification(
            conn,
            f"notif_admin_alert_{uuid.uuid4().hex}",
            int(admin_user_id),
            type_value,
            title,
            message,
            normalized_source,
            None,
            int(now_ms),
            int(max_per_user),
        )
        created_count += 1
    return created_count
