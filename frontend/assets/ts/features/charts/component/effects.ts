/* SoAI - Charts feature component effects [frontend/assets/ts/features/charts/component/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';
import { CHART_EVENT_NAMES } from '@features/charts/component/chartComponentStatics.ts';
import type { ChartOptionValue } from '@features/charts/chartTypes.ts';
import { monotonicMs } from '@core/time/clock.ts';
import type { ComponentEventDetail, EventHandler } from '@features/charts/component/chartComponentTypes.ts';

type ChartEventDetail = ComponentEventDetail | undefined;

interface ChartEventHost {
    eventHandlers: Map<string, EventHandler[]> | null;
    emit: <TDetail>(eventName: string, detail?: TDetail | null) => void;
}

interface ThrottleTimerHost {
    setTimeout: (callback: () => void, delay: number) => number | null;
    clearTimer: (timerId: number | null | undefined) => void;
}

const addChartEventListener = (host: ChartEventHost, eventName: string, handler: EventHandler | null | undefined): void => {
    if (!CHART_EVENT_NAMES.has(eventName) || !isFunction(handler) || !host.eventHandlers) {
        return;
    }
    const handlers = host.eventHandlers.get(eventName) ?? [];
    host.eventHandlers.set(eventName, [...handlers, handler]);
};

const removeChartEventListener = (host: ChartEventHost, eventName: string, handler?: EventHandler | null): void => {
    if (!CHART_EVENT_NAMES.has(eventName) || !host.eventHandlers || !host.eventHandlers.has(eventName)) {
        return;
    }
    if (!handler) {
        host.eventHandlers.delete(eventName);
        return;
    }

    const nextHandlers = (host.eventHandlers.get(eventName) ?? []).filter((existingHandler) => existingHandler !== handler);
    if (nextHandlers.length > 0) {
        host.eventHandlers.set(eventName, nextHandlers);
        return;
    }
    host.eventHandlers.delete(eventName);
};

const emitChartEvent = (host: ChartEventHost, eventName: string, data?: ChartEventDetail): void => {
    if (CHART_EVENT_NAMES.has(eventName) && host.eventHandlers) {
        const handlers = host.eventHandlers.get(eventName) ?? [];
        handlers.forEach((handler) => handler(data));
    }
    host.emit(eventName, data);
};

type ThrottleArgument = ChartOptionValue | undefined;

const createThrottledInvoker = <T extends readonly ThrottleArgument[]>(host: ThrottleTimerHost, functionValue: (...inputArguments: T) => void, wait: number): ((...inputArguments: T) => void) => {
    let throttleTimerId: number | null = null;
    let last = 0;
    return (...inputArguments: T): void => {
        const now = monotonicMs();
        const remaining = wait - (now - last);
        if (throttleTimerId !== null) {
            host.clearTimer(throttleTimerId);
            throttleTimerId = null;
        }
        if (remaining <= 0) {
            last = now;
            functionValue(...inputArguments);
        } else {
            throttleTimerId = host.setTimeout(() => {
                last = monotonicMs();
                functionValue(...inputArguments);
            }, remaining);
        }
    };
};

export { addChartEventListener, createThrottledInvoker, emitChartEvent, removeChartEventListener };
export type { ChartEventDetail };
