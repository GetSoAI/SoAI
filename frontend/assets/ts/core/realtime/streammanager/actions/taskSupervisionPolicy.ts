/* SoAI - Shared realtime task supervision policy [frontend/assets/ts/core/realtime/streammanager/actions/taskSupervisionPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { daysToMs, secondsToMs } from '@core/time/durations.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';

const DEFAULT_TASK_WATCH_TIMEOUT_MS = daysToMs(1);
const TASK_SNAPSHOT_POLL_INTERVAL_MS = secondsToMs(5);
const TASK_SNAPSHOT_MAX_RETRY_DELAY_MS = secondsToMs(60);

const resolveTaskWatchTimeoutMs = (timeoutMs: number | undefined): number => {
    if (timeoutMs === undefined) return DEFAULT_TASK_WATCH_TIMEOUT_MS;
    if (!isFiniteNumber(timeoutMs) || timeoutMs <= 0) {
        throw new RangeError('Task watch timeout must be a positive finite number');
    }
    return timeoutMs;
};

const resolveTaskSnapshotRetryDelayMs = (consecutiveFailureCount: number): number => {
    if (!Number.isSafeInteger(consecutiveFailureCount) || consecutiveFailureCount <= 0) {
        throw new RangeError('Task snapshot failure count must be a positive safe integer');
    }
    const exponent = Math.min(consecutiveFailureCount - 1, 4);
    return Math.min(TASK_SNAPSHOT_POLL_INTERVAL_MS * 2 ** exponent, TASK_SNAPSHOT_MAX_RETRY_DELAY_MS);
};

const shouldReportTaskSnapshotFailure = (consecutiveFailureCount: number): boolean => {
    return consecutiveFailureCount === 1 || consecutiveFailureCount % 10 === 0;
};

export { DEFAULT_TASK_WATCH_TIMEOUT_MS, TASK_SNAPSHOT_POLL_INTERVAL_MS, resolveTaskSnapshotRetryDelayMs, resolveTaskWatchTimeoutMs, shouldReportTaskSnapshotFailure };
