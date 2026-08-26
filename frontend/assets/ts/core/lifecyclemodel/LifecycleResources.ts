/* SoAI - Frontend lifecycle resource ownership [frontend/assets/ts/core/lifecyclemodel/LifecycleResources.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createModuleLogger, createSafeInvoker, type ModuleLogger, type SafeInvoker } from '@core/moduleContext.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { DisposableResource } from '@core/resourcetracker/types.ts';
import { isFunction, isNullOrUndefined, isNumber, isObject, isThenable } from '@core/typeGuards.ts';
import type { EventHandler, TimerOptions } from '@core/lifecyclemodel/types.ts';

const MODULE = 'LifecycleModel';
const log: ModuleLogger = createModuleLogger(MODULE, { defaultLevel: 'warn' });
const safeInvoke: SafeInvoker = createSafeInvoker(log, 'warn');

class LifecycleResources {
    readonly tracker = new ResourceTracker();

    addEventListener(target: EventTarget | null | undefined, event: string, handler: EventHandler, options: AddEventListenerOptions = {}): () => void {
        if (!target) throw new Error('Event target is required');
        if (!isFunction(handler)) throw new Error('Event handler must be a function');
        return this.tracker.addEventListener(target, event, handler, options);
    }

    removeEventListener(target: EventTarget | null | undefined, event: string, handler: EventHandler, options: EventListenerOptions = {}): void {
        if (!target || !isFunction(handler)) return;
        try {
            this.tracker.removeEventListener(target, event, handler, options);
        } catch (error) {
            errorHandler.warn(MODULE, 'removeEventListener failed', ensureError(error));
        }
    }

    setTimer(callback: (() => void | Promise<void>) | undefined, delay: number, options?: TimerOptions): number | null {
        if (!isFunction(callback)) return null;
        if (options && !isObject(options)) throw new TypeError('options must be an object');
        const { repeat = false, immediate = false } = options || {};
        const safeDelay = isNumber(delay) && !Number.isNaN(delay) ? delay : 0;
        const timerRunner = (): void => {
            const result = safeInvoke(callback, [], 'Timer callback failed');
            if (isThenable(result)) void Promise.resolve(result).catch((error) => errorHandler.error(MODULE, 'Async timer callback failed', ensureError(error)));
        };
        const timerId = this.tracker[repeat ? 'setInterval' : 'setTimeout'](timerRunner, safeDelay);
        if (immediate) timerRunner();
        return timerId;
    }

    clearTimer(timerId: number | null | undefined): void {
        if (!isNullOrUndefined(timerId)) this.tracker.clearTimer(timerId);
    }

    track<T extends DisposableResource>(resource: T, cleanup?: (value: T) => void | Promise<void>): T {
        return this.tracker.track(resource, cleanup);
    }

    untrack(resource: DisposableResource): void {
        this.tracker.untrack(resource);
    }

    async cleanup(): Promise<void> {
        try {
            await this.tracker.cleanup();
        } catch (error) {
            errorHandler.error(MODULE, 'cleanup failed', ensureError(error));
        }
    }
}

export { LifecycleResources };
