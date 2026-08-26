/* SoAI - Shared timers scheduled handlers [frontend/assets/ts/core/timers/scheduledHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

type ScheduledHandler<TArguments extends (JsonValue | undefined)[]> = ((...inputArguments: TArguments) => void) & { cancel: () => void };

interface ScheduledHandlerTimers {
    setTimer: (callback: () => void, delayMs: number) => number;
    clearTimer: (timerId: number) => void;
    nowMs: () => number;
}

const requireDelayMs = (delayMs: number): number => {
    if (!Number.isFinite(delayMs) || delayMs < 0) {
        throw new Error('Scheduled handler delay must be a finite non-negative number.');
    }
    return delayMs;
};

const requireNowMs = (nowMs: number): number => {
    if (!Number.isFinite(nowMs)) {
        throw new Error('Scheduled handler clock must return a finite number.');
    }
    return nowMs;
};

const createDebouncedHandler = <TArguments extends (JsonValue | undefined)[]>(functionValue: (...inputArguments: TArguments) => void, delayMs: number, timers: ScheduledHandlerTimers): ScheduledHandler<TArguments> => {
    const resolvedDelayMs = requireDelayMs(delayMs);
    let timerId: number | null = null;
    return Object.assign(
        (...inputArguments: TArguments): void => {
            if (timerId !== null) {
                timers.clearTimer(timerId);
            }
            timerId = timers.setTimer(() => {
                timerId = null;
                functionValue(...inputArguments);
            }, resolvedDelayMs);
        },
        {
            cancel: (): void => {
                if (timerId === null) {
                    return;
                }
                timers.clearTimer(timerId);
                timerId = null;
            }
        }
    );
};

const createThrottledHandler = <TArguments extends (JsonValue | undefined)[]>(functionValue: (...inputArguments: TArguments) => void, delayMs: number, timers: ScheduledHandlerTimers): ScheduledHandler<TArguments> => {
    const resolvedDelayMs = requireDelayMs(delayMs);
    let lastRunAtMs: number | null = null;
    let timerId: number | null = null;
    let queuedArguments: TArguments | null = null;
    return Object.assign(
        (...inputArguments: TArguments): void => {
            const nowMs = requireNowMs(timers.nowMs());
            const elapsedMs = lastRunAtMs === null ? resolvedDelayMs : nowMs - lastRunAtMs;
            if (elapsedMs >= resolvedDelayMs) {
                lastRunAtMs = nowMs;
                queuedArguments = null;
                if (timerId !== null) {
                    timers.clearTimer(timerId);
                    timerId = null;
                }
                functionValue(...inputArguments);
                return;
            }
            queuedArguments = inputArguments;
            if (timerId !== null) {
                return;
            }
            timerId = timers.setTimer(() => {
                lastRunAtMs = requireNowMs(timers.nowMs());
                timerId = null;
                const latestArguments = queuedArguments;
                queuedArguments = null;
                if (latestArguments) {
                    functionValue(...latestArguments);
                }
            }, resolvedDelayMs - elapsedMs);
        },
        {
            cancel: (): void => {
                queuedArguments = null;
                if (timerId === null) {
                    return;
                }
                timers.clearTimer(timerId);
                timerId = null;
            }
        }
    );
};

export { createDebouncedHandler, createThrottledHandler };
export type { ScheduledHandler, ScheduledHandlerTimers };
