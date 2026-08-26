/* SoAI - Shared resource tracker service [frontend/assets/ts/core/resourcetracker/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { getGlobalScope } from '@core/environment/globalScope.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isFunction, isThenable } from '@core/typeGuards.ts';
import { cleanupTrackedDisposable, clearTrackedTimers, invokeDisposable, safeDispose } from '@core/resourcetracker/actions.ts';
import { toCaptureFlag, toTargetArray } from '@core/resourcetracker/guards.ts';
import type { DisposableMetadata, DisposableResource, EventHandler, EventListenerMetadata, EventListenerOptions, EventTargetContract, EventTargetInput, ResourceSnapshot } from '@core/resourcetracker/types.ts';
import { ensureError } from '@core/errors/coerce.ts';

type NativeTimerHandle = number | ReturnType<typeof setTimeout>;

class ResourceTracker {
    eventListeners: Set<EventListenerMetadata>;
    timeouts: Set<number>;
    intervals: Set<number>;
    animationFrames: Set<number>;
    disposables: Set<DisposableMetadata>;
    #nativeTimeoutsById: Map<number, NativeTimerHandle>;
    #nativeIntervalsById: Map<number, NativeTimerHandle>;
    #nextOpaqueTimerId: number;

    constructor() {
        this.eventListeners = new Set();
        this.timeouts = new Set();
        this.intervals = new Set();
        this.animationFrames = new Set();
        this.disposables = new Set();
        this.#nativeTimeoutsById = new Map();
        this.#nativeIntervalsById = new Map();
        this.#nextOpaqueTimerId = 1;
    }

    addEventListener(element: EventTargetInput, event: string, handler: EventHandler, options: EventListenerOptions | boolean = {}): () => void {
        if (!event) {
            throw new Error('Event name is required');
        }
        if (!isFunction(handler)) {
            throw new Error('Event handler must be a function');
        }
        const targets = toTargetArray(element);
        if (targets.length === 0) {
            throw new Error('Event target is required');
        }
        const uniqueTargets: EventTargetContract[] = [];
        const seen = new Set<EventTargetContract>();
        for (const target of targets) {
            if (!isFunction(target.addEventListener)) {
                continue;
            }
            if (seen.has(target)) {
                continue;
            }
            seen.add(target);
            uniqueTargets.push(target);
        }

        if (uniqueTargets.length === 0) throw new Error('No valid event targets available');
        const records: EventListenerMetadata[] = [];
        const wrappedHandler: EventListener = (eventObject: Event) => {
            try {
                const result = handler(eventObject);
                if (isThenable(result)) {
                    Promise.resolve(result).catch((handlerError: Error) => {
                        errorHandler.error('ResourceTracker', 'Async event handler failed', handlerError);
                    });
                }
            } catch (handlerError) {
                const runtimeError = ensureError(handlerError);
                errorHandler.error('ResourceTracker', 'Event handler failed', runtimeError);
            }
        };

        for (const target of uniqueTargets) {
            target.addEventListener(event, wrappedHandler, options);
            const metadata: EventListenerMetadata = {
                element: target,
                event,
                handler: wrappedHandler,
                options,
                originalHandler: handler
            };
            this.eventListeners.add(metadata);
            records.push(metadata);
        }

        return () => {
            for (const metadata of records) {
                const target = metadata.element;
                target.removeEventListener?.(event, wrappedHandler, options);
                this.eventListeners.delete(metadata);
            }
        };
    }

    removeEventListener(element: EventTargetInput, event: string, handler: EventHandler, options: EventListenerOptions | boolean = {}): void {
        if (!event) {
            throw new Error('Event name is required');
        }
        if (!isFunction(handler)) {
            throw new Error('Event handler must be a function');
        }

        const targets = toTargetArray(element);
        if (targets.length === 0) throw new Error('Event target is required');
        const captureFlag = toCaptureFlag(options);
        for (const target of targets) {
            if (!isFunction(target.removeEventListener)) {
                continue;
            }
            for (const metadata of Array.from(this.eventListeners)) {
                if (metadata.element !== target) {
                    continue;
                }
                if (metadata.event !== event) {
                    continue;
                }
                if (metadata.originalHandler !== handler) {
                    continue;
                }
                if (toCaptureFlag(metadata.options) !== captureFlag) {
                    continue;
                }

                metadata.element.removeEventListener?.(event, metadata.handler, metadata.options);
                this.eventListeners.delete(metadata);
            }
        }
    }

    setTimeout(callback: (() => void) | undefined, delay: number): number {
        const scope = getGlobalScope();
        const safeDelay = Number.isFinite(delay) ? delay : 0;
        let id = 0;
        const nativeHandle: NativeTimerHandle = scope.setTimeout(() => {
            this.timeouts.delete(id);
            this.#nativeTimeoutsById.delete(id);
            callback?.();
        }, safeDelay);
        id = typeof nativeHandle === 'number' ? nativeHandle : this.#nextOpaqueTimerId++;
        this.#nativeTimeoutsById.set(id, nativeHandle);
        this.timeouts.add(id);
        return id;
    }

    async waitForTimeout(delay: number): Promise<void> {
        await new Promise<void>((resolve) => {
            let timerId = 0;
            const settle = (): void => {
                this.clearTimeout(timerId);
                this.untrack(settle);
                resolve();
            };
            this.track(settle, (trackedSettle) => trackedSettle());
            timerId = this.setTimeout(settle, delay);
        });
    }

    clearTimeout(id: number): void {
        const scope = getGlobalScope();
        const nativeHandle = this.#nativeTimeoutsById.get(id);
        if (nativeHandle !== undefined) {
            scope.clearTimeout(nativeHandle);
            this.#nativeTimeoutsById.delete(id);
        } else {
            scope.clearTimeout(id);
        }
        this.timeouts.delete(id);
    }

    setInterval(callback: (() => void) | undefined, delay: number): number {
        const scope = getGlobalScope();
        const safeDelay = Number.isFinite(delay) ? delay : 0;
        const nativeHandle: NativeTimerHandle = scope.setInterval(() => {
            callback?.();
        }, safeDelay);
        const id = typeof nativeHandle === 'number' ? nativeHandle : this.#nextOpaqueTimerId++;
        this.#nativeIntervalsById.set(id, nativeHandle);
        this.intervals.add(id);
        return id;
    }

    clearInterval(id: number): void {
        const scope = getGlobalScope();
        const nativeHandle = this.#nativeIntervalsById.get(id);
        if (nativeHandle !== undefined) {
            scope.clearInterval(nativeHandle);
            this.#nativeIntervalsById.delete(id);
        } else {
            scope.clearInterval(id);
        }
        this.intervals.delete(id);
    }

    clearTimer(id: number): void {
        this.clearTimeout(id);
        this.clearInterval(id);
    }

    clearAllTimers(): void {
        const scope = getGlobalScope();
        clearTrackedTimers({
            timeouts: this.timeouts,
            intervals: this.intervals,
            animationFrames: this.animationFrames,
            nativeTimeoutsById: this.#nativeTimeoutsById,
            nativeIntervalsById: this.#nativeIntervalsById,
            clearTimeout: (handle) => scope.clearTimeout(handle),
            clearInterval: (handle) => scope.clearInterval(handle),
            cancelAnimationFrame: (frameId) => getCancelAnimationFrame()(frameId)
        });
    }

    requestAnimationFrame(callback: ((timestamp: DOMHighResTimeStamp) => void) | undefined): number {
        const requestAnimationFrame = getRequestAnimationFrame();
        const id = requestAnimationFrame((timestamp: DOMHighResTimeStamp) => {
            this.animationFrames.delete(id);
            callback?.(timestamp);
        });
        this.animationFrames.add(id);
        return id;
    }

    cancelAnimationFrame(id: number): void {
        const cancelAnimationFrame = getCancelAnimationFrame();
        cancelAnimationFrame(id);
        this.animationFrames.delete(id);
    }

    track<T extends DisposableResource>(disposable: T, cleanup?: ((disposable: T) => void | Promise<void>) | undefined): T {
        if (!disposable) return disposable;
        const metadata: DisposableMetadata = {
            disposable,
            cleanup: cleanup ? () => cleanup(disposable) : undefined
        };
        this.disposables.add(metadata);
        return disposable;
    }

    untrack(disposable: DisposableResource): void {
        for (const metadata of this.disposables) {
            if (metadata.disposable === disposable) {
                this.disposables.delete(metadata);
                break;
            }
        }
    }

    snapshot(): ResourceSnapshot {
        return {
            eventListeners: this.eventListeners.size,
            timeouts: this.timeouts.size,
            intervals: this.intervals.size,
            animationFrames: this.animationFrames.size,
            disposables: this.disposables.size
        };
    }

    static async invoke(disposable: DisposableResource): Promise<void> {
        await invokeDisposable(disposable);
    }

    async cleanup(): Promise<void> {
        this.eventListeners.forEach(({ element, event, handler, options }) => {
            try {
                element.removeEventListener?.(event, handler, options);
            } catch (error) {
                errorHandler.warn('ResourceTracker', 'Event listener cleanup failed', ensureError(error));
            }
        });
        this.eventListeners.clear();

        const scope = getGlobalScope();
        clearTrackedTimers({
            timeouts: this.timeouts,
            intervals: this.intervals,
            animationFrames: this.animationFrames,
            nativeTimeoutsById: this.#nativeTimeoutsById,
            nativeIntervalsById: this.#nativeIntervalsById,
            clearTimeout: (handle) => scope.clearTimeout(handle),
            clearInterval: (handle) => scope.clearInterval(handle),
            cancelAnimationFrame: (frameId) => getCancelAnimationFrame()(frameId)
        });

        await Promise.all(
            [...this.disposables].map((metadata) =>
                cleanupTrackedDisposable(metadata, (runtimeError) => {
                    errorHandler.warn('ResourceTracker', 'Disposable cleanup failed', runtimeError);
                })
            )
        );
        this.disposables.clear();
    }
}

export { ResourceTracker, safeDispose };
