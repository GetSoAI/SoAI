/* SoAI - Charts feature history range follow [frontend/assets/ts/features/charts/historyRangeFollow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { minutesToMs } from '@core/time/durations.ts';

interface HistoryRangeFollowInput {
    availableMinutes: readonly number[];
    selectedMinutes: number;
    visibleStartTs: number;
    visibleEndTs: number;
    newestTs: number | null;
    apply(minutes: number): void;
}

const SPAN_TOLERANCE_RATIO = 0.01;

const resolveHistoryRangeForSpan = (availableMinutes: readonly number[], spanMs: number): number | null => {
    const sorted = availableMinutes.filter((minutes) => Number.isFinite(minutes) && minutes > 0).sort((first, second) => first - second);
    if (!Number.isFinite(spanMs) || spanMs <= 0) return null;
    return sorted.find((minutes) => minutesToMs(minutes) >= spanMs * (1 - SPAN_TOLERANCE_RATIO)) ?? sorted[sorted.length - 1] ?? null;
};

const followHistoryRange = ({ availableMinutes, selectedMinutes, visibleStartTs, visibleEndTs, newestTs, apply }: HistoryRangeFollowInput): void => {
    if (newestTs === null || !Number.isFinite(newestTs)) return;
    const minutes = resolveHistoryRangeForSpan(availableMinutes, Math.min(visibleEndTs, newestTs) - visibleStartTs);
    if (minutes !== null && minutes !== selectedMinutes) apply(minutes);
};

export { followHistoryRange };
export type { HistoryRangeFollowInput };
