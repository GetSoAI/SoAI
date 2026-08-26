"""SoAI - Cancellation snapshot construction utilities [backend/core/tasks/cancellation_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from operator import itemgetter
from typing import TYPE_CHECKING

from core.concurrency.protocols import CancellationTokenProtocol
from core.timing.epoch import epoch_seconds_float

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_cancellation_snapshot",
    "build_token_snapshot",
    "sanitize_metadata",
)


def sanitize_metadata(metadata: Mapping[str, JSONValue] | None) -> JSONDict:
    if not metadata:
        return {}
    return {
        metadata_key: (
            metadata_value
            if isinstance(metadata_value, str | int | float | bool) or metadata_value is None
            else repr(metadata_value)
        )
        for metadata_key, metadata_value in metadata.items()
    }


def build_token_snapshot(token: CancellationTokenProtocol) -> JSONDict:
    return {
        "owner": token.owner or "",
        "metadata": sanitize_metadata(token.metadata),
        "cancelled": token.thread_event.is_set(),
        "reason": token.cancellation_reason,
        "token_id": hex(id(token)),
    }


def build_cancellation_snapshot(
    *,
    tokens_copy: Mapping[str, set[CancellationTokenProtocol]],
    reasons_copy: Mapping[str, str],
    order_copy: Sequence[str],
) -> JSONDict:
    snapshot_time = epoch_seconds_float()

    active_details: dict[str, list[JSONDict]] = {}
    for cancellation_id, tokens in tokens_copy.items():
        if not tokens:
            continue
        summaries = [build_token_snapshot(token) for token in tokens]
        summaries.sort(key=itemgetter("owner", "token_id"))
        active_details[cancellation_id] = summaries

    active_details = dict(sorted(active_details.items()))
    active_cancellation_counts: dict[str, int] = {
        cancellation_id: len(token_list) for cancellation_id, token_list in active_details.items()
    }

    cancelled: list[JSONDict] = [
        {
            "cancellation_id": cancellation_id,
            "reason": reasons_copy.get(cancellation_id),
        }
        for cancellation_id in order_copy
    ]
    missing_from_history = sorted(set(reasons_copy).difference(order_copy))
    if missing_from_history:
        cancelled.extend(
            {
                "cancellation_id": cancellation_id,
                "reason": reasons_copy.get(cancellation_id),
            }
            for cancellation_id in missing_from_history
        )

    return {
        "generated_at": snapshot_time,
        "active_cancellation_counts": active_cancellation_counts,
        "active_tokens": active_details,
        "total_active_tokens": sum(active_cancellation_counts.values()),
        "cancelled_cancellations": cancelled,
        "cancelled_cancellation_count": len(cancelled),
    }
