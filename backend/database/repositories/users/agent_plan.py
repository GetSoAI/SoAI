"""SoAI - Agent long plan persistence [backend/database/repositories/users/agent_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.agent.state_payloads import build_persisted_agent_plan_payload
from core.agent.state_record_validation import normalize_agent_plan_record
from core.errors.exceptions import DatabaseError
from database.core.query_execution import query_one_to_dict
from database.repositories.users.agent_state_persistence import (
    RevisionedAgentStateWrite,
    coerce_agent_state_row_identity,
    sync_upsert_revisioned_agent_state_write,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseAgentPlan",)


def _format_plan_row(
    row: SQLiteRowDict | None,
    *,
    conv_id: str,
    user_id: int,
) -> JSONDict | None:
    coerced_row, conv_id, user_id = coerce_agent_state_row_identity(
        row,
        default_conv_id=conv_id,
        default_user_id=user_id,
        invalid_utf8_message="Agent plan row contains invalid utf-8 bytes.",
        operation="database.agent_plan.coerce_row",
    )
    return normalize_agent_plan_record(
        coerced_row,
        conv_id=conv_id,
        user_id=user_id,
        build_error=lambda message: DatabaseError(
            message,
            operation="database.agent_plan.format_row",
        ),
    )


class DatabaseAgentPlan:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def read_plan(self, *, conv_id: str, user_id: int) -> JSONDict | None:
        async def _query(database: aiosqlite.Connection) -> JSONDict | None:
            row = await query_one_to_dict(
                database,
                """
                SELECT conv_id, user_id, revision, updated_at_ms, title, markdown
                FROM webui_agent_plan
                WHERE conv_id = ? AND user_id = ?
                """,
                (conv_id, int(user_id)),
            )
            return _format_plan_row(
                row if isinstance(row, dict) else None,
                conv_id=conv_id,
                user_id=user_id,
            )

        return await self.core.reader.execute_read(_query)

    async def upsert_plan(
        self,
        *,
        conv_id: str,
        user_id: int,
        revision: int,
        updated_at_ms: int,
        title: str | None,
        markdown: str | None,
    ) -> bool:
        normalized = build_persisted_agent_plan_payload(
            conv_id=conv_id,
            user_id=int(user_id),
            revision=int(revision),
            updated_at_ms=int(updated_at_ms),
            title_value=title,
            markdown_value=markdown,
        )
        return await self.core.writer.queue_write_operation(
            sync_upsert_revisioned_agent_state_write,
            RevisionedAgentStateWrite(
                table_name="webui_agent_plan",
                value_columns=("title", "markdown"),
                conv_id=conv_id,
                user_id=int(user_id),
                revision=int(revision),
                updated_at_ms=int(updated_at_ms),
                values=(normalized.title, normalized.markdown),
                require_no_running_turn=False,
            ),
        )

    async def upsert_plan_if_no_running_turn(
        self,
        *,
        conv_id: str,
        user_id: int,
        revision: int,
        updated_at_ms: int,
        title: str | None,
        markdown: str | None,
    ) -> bool:
        normalized = build_persisted_agent_plan_payload(
            conv_id=conv_id,
            user_id=int(user_id),
            revision=int(revision),
            updated_at_ms=int(updated_at_ms),
            title_value=title,
            markdown_value=markdown,
        )
        return await self.core.writer.queue_write_operation(
            sync_upsert_revisioned_agent_state_write,
            RevisionedAgentStateWrite(
                table_name="webui_agent_plan",
                value_columns=("title", "markdown"),
                conv_id=conv_id,
                user_id=int(user_id),
                revision=int(revision),
                updated_at_ms=int(updated_at_ms),
                values=(normalized.title, normalized.markdown),
                require_no_running_turn=True,
            ),
        )
