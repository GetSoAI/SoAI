/* SoAI - Shared resource tracker service [frontend/assets/ts/core/resourcetracker/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { getGlobalScope } from '@core/environment/globalScope.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isFunction, isThenable } from '@core/typeGuards.ts';
import { cleanupTrackedDisposable, clearTrackedEventListeners, clearTrackedTimers, invokeDisposable, safeDispose, settleTrackedDisposables } from '@core/resourcetracker/actions.ts';
import { toCaptureFlag, toTargetArray } from '@core/resourcetracker/guards.ts';
import type { DisposableMetadata, DisposableResource, EventHandler, EventListenerMetadata, EventListenerOptions, EventTargetContract, EventTargetInput, ResourceSnapshot } from '@core/resourcetracker/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortError } from '@core/errors/abort.ts';

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
    #sealed = false;
    #releaseInvocationDepth = 0;

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
        this.requireActive();
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
            if (this.#sealed) return;
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
        this.requireActive();
        const scope = getGlobalScope();
        const safeDelay = Number.isFinite(delay) ? delay : 0;
        let id = 0;
        const nativeHandle: NativeTimerHandle = scope.setTimeout(() => {
            this.timeouts.delete(id);
            this.#nativeTimeoutsById.delete(id);
            if (!this.#sealed) callback?.();
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
        this.requireActive();
        const scope = getGlobalScope();
        const safeDelay = Number.isFinite(delay) ? delay : 0;
        const nativeHandle: NativeTimerHandle = scope.setInterval(() => {
            if (!this.#sealed) callback?.();
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
        const failures = clearTrackedTimers({
            timeouts: this.timeouts,
            intervals: this.intervals,
            animationFrames: this.animationFrames,
            nativeTimeoutsById: this.#nativeTimeoutsById,
            nativeIntervalsById: this.#nativeIntervalsById,
            clearTimeout: (handle) => scope.clearTimeout(handle),
            clearInterval: (handle) => scope.clearInterval(handle),
            cancelAnimationFrame: (frameId) => getCancelAnimationFrame()(frameId)
        });
        if (failures.length) throw new AggregateError(failures, 'Timer release incomplete');
    }

    requestAnimationFrame(callback: ((timestamp: DOMHighResTimeStamp) => void) | undefined): number {
        this.requireActive();
        const requestAnimationFrame = getRequestAnimationFrame();
        const id = requestAnimationFrame((timestamp: DOMHighResTimeStamp) => {
            if (this.animationFrames.delete(id) && !this.#sealed) callback?.(timestamp);
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
        if (this.#sealed) {
            void this.#release(metadata).catch((error) => {
                errorHandler.warn('ResourceTracker', 'Late resource release failed', ensureError(error));
            });
            this.requireActive();
        }
        return disposable;
    }

    untrack(disposable: DisposableResource): void {
        for (const metadata of this.disposables) {
            if (metadata.disposable === disposable) {
                if (!metadata.completion) this.disposables.delete(metadata);
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

    seal(): void {
        this.#sealed = true;
    }

    requireActive(): void {
        if (this.#sealed) throw createAbortError('Resource owner is sealed');
    }

    async dispose(): Promise<void> {
        this.seal();
        await this.cleanup({ requireComplete: true });
    }

    async #release(metadata: DisposableMetadata): Promise<Error | null> {
        let completion: Promise<Error | null>;
        this.#releaseInvocationDepth += 1;
        try {
            completion = cleanupTrackedDisposable(metadata, (error) => errorHandler.warn('ResourceTracker', 'Disposable cleanup failed', error));
        } finally {
            this.#releaseInvocationDepth -= 1;
        }
        const failure = await completion;
        if (!failure) this.disposables.delete(metadata);
        return failure;
    }

    async cleanup({ requireComplete = false }: { requireComplete?: boolean } = {}): Promise<void> {
        if (this.#releaseInvocationDepth > 0) return;
        const failures = clearTrackedEventListeners(this.eventListeners, (error) => errorHandler.warn('ResourceTracker', 'Event listener cleanup failed', error));
        try {
            this.clearAllTimers();
        } catch (error) {
            const failure = ensureError(error);
            failures.push(failure);
            errorHandler.warn('ResourceTracker', 'Timer cleanup failed', failure);
        }
        failures.push(...(await settleTrackedDisposables(this.disposables, (metadata) => this.#release(metadata), requireComplete && this.#sealed)));
        if (requireComplete && failures.length) throw new AggregateError(failures, 'Resource release incomplete');
    }
}

export { ResourceTracker, safeDispose };
