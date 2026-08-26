"""SoAI - Activity-budgeted conversation message window selection [backend/database/repositories/users/message_window_budget_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from database.repositories.users.message_window_activity_counts import (
    load_message_window_activity_counts,
)
from database.repositories.users.message_window_around_candidate_queries import (
    load_around_message_window_candidates,
)
from database.repositories.users.message_window_candidate_queries import (
    LogicalMessageIdentity,
    load_linear_message_window_candidates,
)

if TYPE_CHECKING:
    from core.conversations.conversation_message_window import (
        ConversationMessageWindowDirection,
    )

__all__ = ("MessageWindowIdentitySelection", "select_message_window_identities")

MAX_MESSAGE_WINDOW_LOGICAL_ACTIVITIES = 50
ATOMIC_TURN_MESSAGE_COUNT = 2


@dataclass(frozen=True, slots=True)
class MessageWindowIdentitySelection:
    non_assistant_message_ids: tuple[int, ...]
    assistant_turn_at_ms_values: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _LogicalGroup:
    identities: tuple[LogicalMessageIdentity, ...]
    logical_activity_count: int


def _build_groups(
    identities: list[LogicalMessageIdentity],
    activity_counts: dict[int, int],
) -> list[_LogicalGroup]:
    groups: list[_LogicalGroup] = []
    index = 0
    while index < len(identities):
        identity = identities[index]
        next_identity = identities[index + 1] if index + 1 < len(identities) else None
        if (
            identity.role == "user"
            and next_identity is not None
            and next_identity.role == "assistant"
        ):
            assistant_turn_at_ms = next_identity.assistant_turn_at_ms
            groups.append(
                _LogicalGroup(
                    identities=(identity, next_identity),
                    logical_activity_count=(
                        activity_counts.get(assistant_turn_at_ms, 0)
                        if assistant_turn_at_ms is not None
                        else 0
                    ),
                ),
            )
            index += 2
            continue
        groups.append(
            _LogicalGroup(
                identities=(identity,),
                logical_activity_count=(
                    activity_counts.get(identity.assistant_turn_at_ms, 0)
                    if identity.assistant_turn_at_ms is not None
                    else 0
                ),
            ),
        )
        index += 1
    return groups


def _admit_linear_groups(
    groups: list[_LogicalGroup],
    *,
    direction: ConversationMessageWindowDirection,
    limit: int,
) -> list[_LogicalGroup]:
    traversal = list(reversed(groups)) if direction in ("tail", "before") else groups
    selected: list[_LogicalGroup] = []
    selected_message_count = 0
    selected_activity_count = 0
    for group in traversal:
        next_message_count = selected_message_count + len(group.identities)
        next_activity_count = selected_activity_count + group.logical_activity_count
        if selected and (
            next_message_count > limit
            or next_activity_count > MAX_MESSAGE_WINDOW_LOGICAL_ACTIVITIES
        ):
            break
        selected.append(group)
        selected_message_count = next_message_count
        selected_activity_count = next_activity_count
    return selected


def _find_anchor_group_index(
    groups: list[_LogicalGroup],
    anchor: LogicalMessageIdentity,
) -> int:
    for index, group in enumerate(groups):
        for identity in group.identities:
            if identity.message_id == anchor.message_id:
                return index
            if (
                anchor.assistant_turn_at_ms is not None
                and identity.assistant_turn_at_ms == anchor.assistant_turn_at_ms
            ):
                return index
    raise ValidationError("around anchor group was not found.")


def _admit_around_groups(
    groups: list[_LogicalGroup],
    *,
    anchor: LogicalMessageIdentity,
    limit: int,
) -> list[_LogicalGroup]:
    anchor_index = _find_anchor_group_index(groups, anchor)
    selected: list[_LogicalGroup] = [groups[anchor_index]]
    selected_message_count = len(selected[0].identities)
    selected_activity_count = selected[0].logical_activity_count
    older_index = anchor_index - 1
    newer_index = anchor_index + 1
    choose_older = True
    older_blocked = older_index < 0
    newer_blocked = newer_index >= len(groups)
    while not (older_blocked and newer_blocked):
        select_older = choose_older and not older_blocked
        if not select_older and newer_blocked:
            select_older = True
        candidate_index = older_index if select_older else newer_index
        group = groups[candidate_index]
        next_message_count = selected_message_count + len(group.identities)
        next_activity_count = selected_activity_count + group.logical_activity_count
        if (
            next_message_count > limit
            or next_activity_count > MAX_MESSAGE_WINDOW_LOGICAL_ACTIVITIES
        ):
            if select_older:
                older_blocked = True
            else:
                newer_blocked = True
            choose_older = not choose_older
            continue
        selected.append(group)
        selected_message_count = next_message_count
        selected_activity_count = next_activity_count
        if select_older:
            older_index -= 1
            older_blocked = older_index < 0
        else:
            newer_index += 1
            newer_blocked = newer_index >= len(groups)
        choose_older = not choose_older
    return selected


def _selection_from_groups(
    groups: list[_LogicalGroup],
) -> MessageWindowIdentitySelection:
    message_ids: set[int] = set()
    assistant_turns: set[int] = set()
    for group in groups:
        for identity in group.identities:
            if identity.assistant_turn_at_ms is None:
                message_ids.add(identity.message_id)
            else:
                assistant_turns.add(identity.assistant_turn_at_ms)
    return MessageWindowIdentitySelection(
        non_assistant_message_ids=tuple(sorted(message_ids)),
        assistant_turn_at_ms_values=tuple(sorted(assistant_turns)),
    )


async def select_message_window_identities(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    direction: ConversationMessageWindowDirection,
    limit: int,
    cursor_created_at_ms: int | None,
    cursor_id: int | None,
    anchor_created_at_ms: int | None,
    anchor_id: int | None,
) -> MessageWindowIdentitySelection:
    candidate_limit = limit + ATOMIC_TURN_MESSAGE_COUNT
    anchor: LogicalMessageIdentity | None = None
    if direction == "around":
        identities, anchor = await load_around_message_window_candidates(
            database,
            conv_id=conv_id,
            candidate_limit=candidate_limit,
            anchor_created_at_ms=anchor_created_at_ms,
            anchor_id=anchor_id,
        )
    else:
        identities = await load_linear_message_window_candidates(
            database,
            conv_id=conv_id,
            direction=direction,
            candidate_limit=candidate_limit,
            cursor_created_at_ms=cursor_created_at_ms,
            cursor_id=cursor_id,
        )
    assistant_turns = sorted(
        {
            identity.assistant_turn_at_ms
            for identity in identities
            if identity.assistant_turn_at_ms is not None
        },
    )
    activity_counts = await load_message_window_activity_counts(
        database,
        conv_id=conv_id,
        assistant_turn_at_ms_values=assistant_turns,
    )
    groups = _build_groups(identities, activity_counts)
    selected_groups = (
        _admit_around_groups(groups, anchor=anchor, limit=limit)
        if anchor is not None
        else _admit_linear_groups(groups, direction=direction, limit=limit)
    )
    return _selection_from_groups(selected_groups)
