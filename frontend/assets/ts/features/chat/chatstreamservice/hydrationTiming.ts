/* SoAI - Chat stream hydration timing constants [frontend/assets/ts/features/chat/chatstreamservice/hydrationTiming.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { monotonicMs } from '@core/time/clock.ts';

const CHAT_STREAM_HYDRATION_DEADLINE_MS = 5000;
const CHAT_STREAM_HYDRATION_RETRY_DELAYS_MS = [750, 1000, 1500, 1750];

const resolveHydrationDeadlineAtMs = (): number => monotonicMs() + CHAT_STREAM_HYDRATION_DEADLINE_MS;

const normalizeRequiredHydrationSequence = (requiredSequence: number): number => (Number.isInteger(requiredSequence) && requiredSequence >= 0 ? requiredSequence : 0);

const resolveHydrationRetryDelayMs = (attemptIndex: number, deadlineAtMs: number): number => {
    const remainingMs = deadlineAtMs - monotonicMs();
    if (remainingMs <= 0) {
        return 0;
    }
    const normalizedAttemptIndex = Number.isInteger(attemptIndex) && attemptIndex >= 0 ? attemptIndex : 0;
    const retryIndex = Math.min(normalizedAttemptIndex, CHAT_STREAM_HYDRATION_RETRY_DELAYS_MS.length - 1);
    const retryDelayMs = CHAT_STREAM_HYDRATION_RETRY_DELAYS_MS[retryIndex] ?? 0;
    return Math.min(retryDelayMs, remainingMs);
};

export { normalizeRequiredHydrationSequence, resolveHydrationDeadlineAtMs, resolveHydrationRetryDelayMs };
