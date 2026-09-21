/* SoAI - Chat page visible activity duration registry ownership [frontend/assets/ts/pages/chat/controllers/page/durations/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { monotonicMs, serverEpochMs } from '@core/time/clock.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/public.ts';
import { ActivityDurationRuntime } from '@pages/chat/controllers/page/durations/ActivityDurationRuntime.ts';

type ActivityDurationRegistryTimerPort = {
    setTimer(callback: () => void, delayMs: number): number;
    clearTimer(timerId: number): void;
};

type ActivityDurationRegistryRecord = {
    conversationId: string;
    runtime: ActivityDurationRuntime;
};

const registryByViewport = new WeakMap<HTMLElement, ActivityDurationRegistryRecord>();

const initializeActivityDurationRegistry = (inputArguments: { viewport: HTMLElement; root: Element; conversationId: string; timers: ActivityDurationRegistryTimerPort; getDisplayMode: () => ChatActivityDurationDisplayMode }): void => {
    const current = registryByViewport.get(inputArguments.viewport);
    let record = current;
    if (record && record.conversationId !== inputArguments.conversationId) {
        record.runtime.dispose();
        registryByViewport.delete(inputArguments.viewport);
        record = undefined;
    }
    if (!record) {
        const runtime = new ActivityDurationRuntime({
            viewport: inputArguments.viewport,
            conversationId: inputArguments.conversationId,
            nowEpochMs: serverEpochMs,
            nowMonotonicMs: monotonicMs,
            setTimer: (callback, delayMs) => inputArguments.timers.setTimer(callback, delayMs),
            clearTimer: (timerId) => inputArguments.timers.clearTimer(timerId),
            getDisplayMode: inputArguments.getDisplayMode
        });
        record = {
            conversationId: inputArguments.conversationId,
            runtime
        };
        registryByViewport.set(inputArguments.viewport, record);
    }
    record.runtime.reconcile(inputArguments.root, inputArguments.conversationId);
};

const reconcileActivityDurationRegistry = (inputArguments: { viewport: HTMLElement; root: Element; conversationId: string }): void => {
    const record = registryByViewport.get(inputArguments.viewport);
    if (!record || record.conversationId !== inputArguments.conversationId) {
        return;
    }
    record.runtime.reconcile(inputArguments.root, inputArguments.conversationId);
};

const disposeActivityDurationRegistry = (viewport: HTMLElement): void => {
    const record = registryByViewport.get(viewport);
    if (!record) {
        return;
    }
    record.runtime.dispose();
    registryByViewport.delete(viewport);
};

export { disposeActivityDurationRegistry, initializeActivityDurationRegistry, reconcileActivityDurationRegistry };
export type { ActivityDurationRegistryTimerPort };
