"""SoAI - Database schema: WebUI notifications [backend/database/schema_scripts/notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.notifications.notification_contracts import (
    NOTIFICATION_TEMPLATE_SQL_VALUES,
    NOTIFICATION_TEXT_TYPE_SQL_VALUES,
    NOTIFICATION_TYPE_SQL_VALUES,
    NotificationTemplateId,
    resolve_notification_template_required_params,
)
from core.validation.epoch import EPOCH_MS_MIN

__all__ = ("apply_notifications_schema",)

NOTIFICATIONS_TABLE = "webui_notifications"


def _build_notification_text_check(
    *,
    column: str,
    text_type_clause: str,
    template_clause: str,
    template_params_check: str,
) -> str:
    return f"""
        CHECK (
            CASE
                WHEN json_valid({column}) THEN
                    coalesce(json_type({column}), '') = 'object'
                    AND coalesce(json_extract({column}, '$.text_type'), '') IN ({text_type_clause})
                    AND (
                        (
                            coalesce(json_extract({column}, '$.text_type'), '') = 'text'
                            AND coalesce(json_type({column}, '$.text'), '') = 'text'
                            AND length(trim(coalesce(json_extract({column}, '$.text'), ''))) > 0
                        )
                        OR (
                            coalesce(json_extract({column}, '$.text_type'), '') = 'template'
                            AND coalesce(json_type({column}, '$.template'), '') = 'text'
                            AND coalesce(json_extract({column}, '$.template'), '') IN ({template_clause})
                            AND ({template_params_check})
                        )
                    )
                ELSE
                    0
            END
        )
    """


def _build_notifications_table_sql(
    *,
    table_name: str,
    type_check_clause: str,
    title_check: str,
    message_check: str,
) -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ({type_check_clause})),
            title TEXT NOT NULL {title_check},
            message TEXT NOT NULL {message_check},
            source TEXT,
            link_json TEXT CHECK(link_json IS NULL OR json_valid(link_json)),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            read_at_ms INTEGER,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        )
        STRICT
        """


def _apply_notifications_table(
    conn: sqlite3.Connection,
    *,
    type_check_clause: str,
    title_check: str,
    message_check: str,
) -> None:
    target_sql = _build_notifications_table_sql(
        table_name=NOTIFICATIONS_TABLE,
        type_check_clause=type_check_clause,
        title_check=title_check,
        message_check=message_check,
    )
    conn.execute(target_sql)


def apply_notifications_schema(conn: sqlite3.Connection) -> None:
    templates_by_required_params: dict[frozenset[str], list[str]] = {}
    for template_id in NotificationTemplateId:
        required = resolve_notification_template_required_params(template_id)
        templates = templates_by_required_params.get(required)
        if templates is None:
            templates = []
            templates_by_required_params[required] = templates
        templates.append(template_id.value)
    for required_keys in templates_by_required_params:
        if len(required_keys) > 2:
            raise StateError("Notification template params SQL contract is invalid.")
        for key in required_keys:
            if not key.strip():
                raise StateError("Notification template params SQL contract is invalid.")

    type_check_clause = ", ".join(f"'{value}'" for value in NOTIFICATION_TYPE_SQL_VALUES)
    text_type_clause = ", ".join(f"'{value}'" for value in NOTIFICATION_TEXT_TYPE_SQL_VALUES)
    template_clause = ", ".join(f"'{value}'" for value in NOTIFICATION_TEMPLATE_SQL_VALUES)

    def _build_param_check(*, column: str, required_keys: tuple[str, ...]) -> str:
        obj_check = f"coalesce(json_type({column}, '$.params'), '') = 'object'"
        if not required_keys:
            return f"{obj_check} AND json(json_extract({column}, '$.params')) = '{{}}'"
        key_checks: list[str] = []
        remove_expr = f"json_extract({column}, '$.params')"
        for key in required_keys:
            key_checks.append(
                f"coalesce(json_type({column}, '$.params.{key}'), '') = 'text' AND length(trim(coalesce(json_extract({column}, '$.params.{key}'), ''))) > 0",
            )
            remove_expr = f"json_remove({remove_expr}, '$.{key}')"
        return f"{obj_check} AND {' AND '.join(key_checks)} AND json({remove_expr}) = '{{}}'"

    def _build_template_params_check(*, column: str) -> str:
        blocks: list[str] = []
        for required_set, templates in sorted(
            templates_by_required_params.items(),
            key=lambda item: (len(item[0]), sorted(item[0])),
        ):
            template_list = tuple(sorted(templates))
            if not template_list:
                raise StateError("Notification template params SQL contract is invalid.")
            template_group_clause = ", ".join(f"'{value}'" for value in template_list)
            required_keys = tuple(sorted(required_set))
            param_check = _build_param_check(column=column, required_keys=required_keys)
            template_expr = (
                f"coalesce(json_extract({column}, '$.template'), '') IN ({template_group_clause})"
            )
            blocks.append(f"({template_expr} AND {param_check})")
        if not blocks:
            raise StateError("Notification template params SQL contract is invalid.")
        return " OR ".join(blocks)

    title_check = _build_notification_text_check(
        column="title",
        text_type_clause=text_type_clause,
        template_clause=template_clause,
        template_params_check=_build_template_params_check(column="title"),
    )
    message_check = _build_notification_text_check(
        column="message",
        text_type_clause=text_type_clause,
        template_clause=template_clause,
        template_params_check=_build_template_params_check(column="message"),
    )
    _apply_notifications_table(
        conn,
        type_check_clause=type_check_clause,
        title_check=title_check,
        message_check=message_check,
    )
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_webui_notifications_user_created
        ON webui_notifications (user_id, created_at_ms DESC)
        """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_webui_notifications_user_read
        ON webui_notifications (user_id, read_at_ms)
        """)
