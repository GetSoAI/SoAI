"""SoAI - Communications sync actor helpers [backend/app/background/communications_sync_actor_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.timing.epoch import epoch_ms
from core.timing.retry_backoff import compute_exponential_backoff_milliseconds
from core.types.json import JSONDict

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.mcp.protocols_main import MCPServerProtocol

__all__ = (
    "SyncBackoffState",
    "build_calendar_account_labels",
    "clear_sync_backoff",
    "extract_account_id",
    "extract_accounts",
    "extract_user_ids",
    "is_sync_due",
    "notify_resource_updated",
    "prune_sync_backoff",
    "register_sync_backoff_failure",
    "supports_action",
)

OPERATION = "app.background.communications_sync_actor.run"


@dataclass(slots=True)
class SyncBackoffState:
    failure_count: int
    next_attempt_at_ms: int


def extract_user_ids(user_rows: list[JSONDict]) -> list[int]:
    user_ids: list[int] = []
    for user_row in user_rows:
        user_id_value = user_row.get("id")
        if not isinstance(user_id_value, int) or user_id_value <= 0:
            raise StateError("Communications user row is invalid.")
        user_ids.append(user_id_value)
    return user_ids


def extract_accounts(payload: JSONDict) -> list[JSONDict]:
    accounts_value = payload.get("items")
    if not isinstance(accounts_value, list):
        raise StateError("Communications account list payload is invalid.")
    count_value = payload.get("count")
    if not isinstance(count_value, int) or count_value != len(accounts_value):
        raise StateError("Communications account list payload is invalid.")
    accounts: list[JSONDict] = []
    for account in accounts_value:
        if not isinstance(account, dict):
            raise StateError("Communications account entry is invalid.")
        extract_account_id(account)
        accounts.append(account)
    return accounts


def extract_account_id(account: JSONDict) -> str:
    account_id_value = account.get("account_id")
    account_id = account_id_value.strip() if isinstance(account_id_value, str) else ""
    if not account_id:
        raise StateError("Communications account entry is missing its account_id.")
    return account_id


def supports_action(account: JSONDict, *, action: str) -> bool:
    supported_actions_value = account.get("supported_actions")
    if not isinstance(supported_actions_value, list):
        raise StateError("Communications account entry is invalid.")
    for supported_action in supported_actions_value:
        if not isinstance(supported_action, str):
            raise StateError("Communications account entry is invalid.")
        normalized = supported_action.strip()
        if not normalized:
            raise StateError("Communications account entry is invalid.")
        if normalized == action:
            return True
    return False


def is_sync_due(
    backoff_state: dict[str, SyncBackoffState],
    *,
    account_id: str,
    now_ms: int | None = None,
) -> bool:
    if not account_id:
        return False
    state = backoff_state.get(account_id)
    if state is None:
        return True
    current_ms = now_ms if isinstance(now_ms, int) and now_ms >= 0 else epoch_ms()
    return current_ms >= state.next_attempt_at_ms


def register_sync_backoff_failure(
    backoff_state: dict[str, SyncBackoffState],
    *,
    account_id: str,
    interval_ms: int,
    now_ms: int | None = None,
) -> int:
    current_ms = now_ms if isinstance(now_ms, int) and now_ms >= 0 else epoch_ms()
    previous = backoff_state.get(account_id)
    failure_count = 1 if previous is None else previous.failure_count + 1
    delay_ms = compute_exponential_backoff_milliseconds(
        min(failure_count - 1, 4),
        base_milliseconds=max(interval_ms, 1),
        maximum_milliseconds=3_600_000,
    )
    backoff_state[account_id] = SyncBackoffState(
        failure_count=failure_count,
        next_attempt_at_ms=current_ms + delay_ms,
    )
    return delay_ms


def clear_sync_backoff(backoff_state: dict[str, SyncBackoffState], *, account_id: str) -> None:
    backoff_state.pop(account_id, None)


def prune_sync_backoff(
    backoff_state: dict[str, SyncBackoffState],
    *,
    active_account_ids: set[str],
) -> None:
    stale_account_ids = [
        account_id for account_id in backoff_state if account_id not in active_account_ids
    ]
    for account_id in stale_account_ids:
        backoff_state.pop(account_id, None)


def build_calendar_account_labels(accounts: list[JSONDict]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for account in accounts:
        account_id = extract_account_id(account)
        label_value = account.get("label")
        label = label_value.strip() if isinstance(label_value, str) else ""
        labels[account_id] = label or account_id
    return labels


async def notify_resource_updated(
    *,
    logger: LoggerProtocol,
    server: MCPServerProtocol | None,
    uri: str,
) -> None:
    if server is None or not server.server_mode_active:
        return
    try:
        await server.notify_resource_updated(uri)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to publish MCP resource update notification (non-critical).",
            operation=OPERATION,
            level="debug",
            details={"uri": uri},
        )
