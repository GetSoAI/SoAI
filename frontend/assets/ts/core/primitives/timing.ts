/* SoAI - Shared primitives timing [frontend/assets/ts/core/primitives/timing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { createDebouncedHandler, createThrottledHandler } from '@core/timers/scheduledHandlers.ts';

const debounce = <TArguments extends JsonValue[]>(functionValue: (...inputArguments: TArguments) => void, delayMs: number): ((...inputArguments: TArguments) => void) => {
    return createDebouncedHandler(functionValue, delayMs, {
        setTimer: (callback, timeoutMs): number => window.setTimeout(callback, timeoutMs),
        clearTimer: (timerId): void => window.clearTimeout(timerId),
        nowMs: monotonicMs
    });
};

const throttle = <TArguments extends JsonValue[]>(functionValue: (...inputArguments: TArguments) => void, delayMs: number): ((...inputArguments: TArguments) => void) => {
    return createThrottledHandler(functionValue, delayMs, {
        setTimer: (callback, timeoutMs): number => window.setTimeout(callback, timeoutMs),
        clearTimer: (timerId): void => window.clearTimeout(timerId),
        nowMs: monotonicMs
    });
};

export { debounce, throttle };
