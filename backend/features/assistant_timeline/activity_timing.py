"""SoAI - Shared assistant timeline activity timing helpers [backend/features/assistant_timeline/activity_timing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.assistant_timeline.models import TimelineActivity

__all__ = (
    "ensure_activity_start_times",
    "resolve_activity_running_duration_ms",
)


def ensure_activity_start_times(
    activity: TimelineActivity,
    *,
    default_started_at_epoch_ms: int,
    default_started_at_monotonic_ms: int,
) -> tuple[int, int]:
    started_at_epoch_ms = activity.started_at_epoch_ms
    started_at_monotonic_ms = activity.started_at_monotonic_ms
    if started_at_monotonic_ms is None or started_at_monotonic_ms < 0:
        started_at_monotonic_ms = int(default_started_at_monotonic_ms)
        activity.started_at_monotonic_ms = started_at_monotonic_ms
    if started_at_epoch_ms is None or started_at_epoch_ms < 0:
        started_at_epoch_ms = int(default_started_at_epoch_ms)
        activity.started_at_epoch_ms = started_at_epoch_ms
    return (int(started_at_epoch_ms), int(started_at_monotonic_ms))


def resolve_activity_running_duration_ms(
    activity: TimelineActivity,
    *,
    now_monotonic_ms: int,
) -> int:
    started_at_monotonic_ms = activity.started_at_monotonic_ms
    if started_at_monotonic_ms is None or started_at_monotonic_ms < 0:
        return max(0, int(activity.duration_ms))
    return max(int(activity.duration_ms), 0, int(now_monotonic_ms) - int(started_at_monotonic_ms))
