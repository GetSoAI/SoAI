/* SoAI - Routed page disposable, timer, and listener ownership [frontend/assets/ts/core/routing/pages/basepagecore/PageResources.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { DisposableResource, EventHandler } from '@core/resourcetracker/types.ts';
import { isFunction, isNullOrUndefined, isNumber, isObject } from '@core/typeGuards.ts';

interface PageTimerOptions {
    immediate?: boolean;
    repeat?: boolean;
}

class PageResources {
    readonly tracker = new ResourceTracker();

    on(target: EventTarget, event: string, handler: EventHandler, options: AddEventListenerOptions = {}): () => void {
        return this.tracker.addEventListener(target, event, handler, options);
    }

    removeListener(target: EventTarget, event: string, handler: EventHandler, options: EventListenerOptions = {}): void {
        this.tracker.removeEventListener(target, event, handler, options);
    }

    track<T extends DisposableResource>(resource: T, cleanup?: (value: T) => void | Promise<void>): T {
        return this.tracker.track(resource, cleanup);
    }

    untrack(resource: DisposableResource): void {
        this.tracker.untrack(resource);
    }

    setTimer(callback: (() => void) | undefined, delay: number, options: PageTimerOptions = {}): number | null {
        if (!isFunction(callback)) {
            return null;
        }
        if (!isObject(options)) {
            throw new TypeError('Page timer options must be an object');
        }
        const safeDelay = isNumber(delay) && !Number.isNaN(delay) ? delay : 0;
        const timerId = options.repeat === true ? this.tracker.setInterval(callback, safeDelay) : this.tracker.setTimeout(callback, safeDelay);
        if (options.immediate === true) {
            callback();
        }
        return timerId;
    }

    setTimeout(callback: (() => void) | undefined, delay: number, options: Omit<PageTimerOptions, 'repeat'> = {}): number | null {
        return this.setTimer(callback, delay, { ...options, repeat: false });
    }

    setInterval(callback: (() => void) | undefined, delay: number, options: Omit<PageTimerOptions, 'repeat'> = {}): number | null {
        return this.setTimer(callback, delay, { ...options, repeat: true });
    }

    clearTimer(timerId: number | null | undefined): void {
        if (!isNullOrUndefined(timerId)) {
            this.tracker.clearTimer(timerId);
        }
    }

    async cleanupTracked(): Promise<void> {
        await this.tracker.cleanup();
    }

    async cleanup(): Promise<void> {
        await this.cleanupTracked();
    }
}

export { PageResources };
export type { PageTimerOptions };
export interface PageResourcesOwnerHost {
    pageResources: PageResources;
}
