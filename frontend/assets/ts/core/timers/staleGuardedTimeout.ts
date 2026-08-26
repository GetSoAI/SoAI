/* SoAI - Shared timers stale guarded timeout [frontend/assets/ts/core/timers/staleGuardedTimeout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type SetTimer = (callback: () => void, delayMs: number) => number | null;
type ClearTimer = (timerId: number | null | undefined) => void;

type StaleGuardedTimeoutArguments = Readonly<{
    currentTimerId: number | null;
    clearTimer: ClearTimer;
    setTimer: SetTimer;
    delayMs: number | null;
    isStale: () => boolean;
    onTick: () => void;
}>;

const scheduleStaleGuardedTimeout = (inputArguments: StaleGuardedTimeoutArguments): number | null => {
    if (inputArguments.currentTimerId !== null) {
        inputArguments.clearTimer(inputArguments.currentTimerId);
    }
    if (inputArguments.delayMs === null) {
        return null;
    }
    const delayMs = inputArguments.delayMs;
    if (!Number.isFinite(delayMs) || delayMs <= 0) {
        return null;
    }
    return inputArguments.setTimer((): void => {
        if (inputArguments.isStale()) {
            return;
        }
        inputArguments.onTick();
    }, delayMs);
};

export { scheduleStaleGuardedTimeout };
