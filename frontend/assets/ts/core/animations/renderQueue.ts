/* SoAI - Coalesced animation-frame render queue [frontend/assets/ts/core/animations/renderQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createAbortError, isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';
import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';
import { scheduleRequiredRender } from '@core/runtime/animationFrames.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isThenable } from '@core/typeGuards.ts';

interface AnimationFrameRenderQueueOptions<TPayload> {
    label: string;
    required?: boolean;
    render?: ((payload: TPayload) => void | Promise<void>) | undefined;
    renderBatch?: ((payloads: readonly TPayload[]) => void | Promise<void>) | undefined;
    merge: (previous: TPayload | null, next: TPayload) => TPayload;
    keyOf?: ((payload: TPayload) => string) | undefined;
    isDisposed?: (() => boolean) | undefined;
    requestAnimationFrame?: ((callback: () => void) => number) | undefined;
    cancelAnimationFrame?: ((id: number) => void) | undefined;
}

type PendingRenderPayload<TPayload> = { value: TPayload };

class AnimationFrameRenderQueue<TPayload> {
    readonly #label: string;
    readonly #required: boolean;
    readonly #render: ((payload: TPayload) => void | Promise<void>) | undefined;
    readonly #renderBatch: ((payloads: readonly TPayload[]) => void | Promise<void>) | undefined;
    readonly #merge: (previous: TPayload | null, next: TPayload) => TPayload;
    readonly #keyOf: ((payload: TPayload) => string) | undefined;
    readonly #isDisposed: () => boolean;
    readonly #requestAnimationFrame: (callback: () => void) => number;
    readonly #cancelAnimationFrame: (id: number) => void;
    #cancelScheduled: (() => void) | null = null;
    #failure: Error | null = null;
    #pendingPayload: PendingRenderPayload<TPayload> | null = null;
    #pendingByKey = new Map<string, TPayload>();
    readonly #idleWaiters = new Set<Deferred<void>>();
    #scheduleGeneration = 0;
    #disposed = false;
    #rendering = false;

    constructor(options: AnimationFrameRenderQueueOptions<TPayload>) {
        this.#label = options.label;
        this.#required = options.required ?? false;
        this.#render = options.render;
        this.#renderBatch = options.renderBatch;
        this.#merge = options.merge;
        this.#keyOf = options.keyOf;
        if (this.#keyOf && !this.#renderBatch) {
            throw new Error('Keyed animation frame render queues require renderBatch');
        }
        if (!this.#keyOf && !this.#render) {
            throw new Error('Animation frame render queues require render');
        }
        this.#isDisposed = options.isDisposed ?? (() => false);
        this.#requestAnimationFrame = options.requestAnimationFrame ?? ((callback) => getRequestAnimationFrame()(callback));
        this.#cancelAnimationFrame = options.cancelAnimationFrame ?? ((id) => getCancelAnimationFrame()(id));
    }

    schedule(payload: TPayload): void {
        if (this.#disposed || this.#isDisposed()) {
            return;
        }
        const key = this.#keyOf?.(payload) ?? null;
        if (this.#keyOf && !key) throw new Error('Animation frame render queue keys must not be empty');
        const previous = key === null ? (this.#pendingPayload === null ? null : this.#pendingPayload.value) : (this.#pendingByKey.get(key) ?? null);
        const merged = this.#merge(previous, payload);
        if (this.#isIdle() || (this.#failure !== null && isAbortError(this.#failure))) this.#failure = null;
        if (key !== null) this.#pendingByKey.set(key, merged);
        else this.#pendingPayload = { value: merged };
        if (this.#cancelScheduled === null && !this.#rendering) this.#requestFlush();
    }

    cancel(): void {
        if (this.#required && !this.#isIdle()) {
            this.#failure = createAbortError('Required render cancelled.');
            this.#settleIdleWaiters();
        }
        this.#scheduleGeneration += 1;
        if (this.#cancelScheduled !== null) {
            this.#cancelScheduled();
            this.#cancelScheduled = null;
        }
        this.#pendingPayload = null;
        this.#pendingByKey.clear();
        this.#resolveIdleIfReady();
    }

    drop(key: string): boolean {
        if (!this.#keyOf) {
            return false;
        }
        const dropped = this.#pendingByKey.delete(key);
        if (this.#pendingByKey.size === 0 && this.#cancelScheduled !== null && !this.#rendering) {
            this.#scheduleGeneration += 1;
            this.#cancelScheduled();
            this.#cancelScheduled = null;
        }
        this.#resolveIdleIfReady();
        return dropped;
    }

    dispose(): void {
        this.#disposed = true;
        this.cancel();
    }

    async waitForIdle(signal: AbortSignal | null = null): Promise<void> {
        throwIfAborted(signal);
        if (this.#disposed || this.#isDisposed()) {
            this.cancel();
            if (this.#required) throw createAbortError('Required render disposed.');
        }
        if (this.#required && this.#failure !== null) throw this.#failure;
        if (this.#isIdle()) return;
        const completion = createDeferred<void>();
        const onAbort = (): void => completion.reject(createAbortError('Render wait aborted.'));
        this.#idleWaiters.add(completion);
        signal?.addEventListener('abort', onAbort, { once: true });
        try {
            await completion.promise;
        } finally {
            this.#idleWaiters.delete(completion);
            signal?.removeEventListener('abort', onAbort);
        }
    }

    #flush(): void {
        this.#cancelScheduled = null;
        const payload = this.#pendingPayload;
        const payloads = Array.from(this.#pendingByKey.values());
        this.#pendingPayload = null;
        this.#pendingByKey.clear();
        if ((payload === null && payloads.length === 0) || this.#disposed || this.#isDisposed()) {
            this.#resolveIdleIfReady();
            return;
        }
        this.#rendering = true;
        const generation = this.#scheduleGeneration;
        try {
            let result: void | Promise<void>;
            if (this.#keyOf && this.#renderBatch) result = this.#renderBatch(payloads);
            else if (payload !== null && this.#render) result = this.#render(payload.value);
            else throw new Error('Animation frame render callback is unavailable');
            if (isThenable(result)) {
                void Promise.resolve(result).then(
                    () => this.#finishRender(),
                    (error) => {
                        this.#recordFailure(ensureError(error), generation);
                        this.#finishRender();
                    }
                );
                return;
            }
        } catch (error) {
            this.#recordFailure(ensureError(error), generation);
        }
        this.#finishRender();
    }

    #recordFailure(error: Error, generation: number): void {
        if (generation !== this.#scheduleGeneration) return;
        if (this.#required) this.#failure ??= error;
        if (!isAbortError(error) && (!this.#required || this.#idleWaiters.size === 0) && claimErrorReporting(error)) {
            errorHandler.error(this.#label, 'Animation frame render failed', error);
        }
    }

    #requestFlush(): void {
        const generation = this.#scheduleGeneration + 1;
        this.#scheduleGeneration = generation;
        const callback = (): void => {
            if (generation !== this.#scheduleGeneration) return;
            this.#flush();
        };
        if (this.#required) {
            this.#cancelScheduled = scheduleRequiredRender(callback, { requestAnimationFrame: this.#requestAnimationFrame, cancelAnimationFrame: this.#cancelAnimationFrame });
        } else {
            const identifier = this.#requestAnimationFrame(callback);
            this.#cancelScheduled = () => this.#cancelAnimationFrame(identifier);
        }
    }

    #finishRender(): void {
        this.#rendering = false;
        if (this.#disposed || this.#isDisposed()) {
            this.#pendingPayload = null;
            this.#pendingByKey.clear();
            this.#resolveIdleIfReady();
            return;
        }
        if ((this.#pendingPayload !== null || this.#pendingByKey.size > 0) && this.#cancelScheduled === null) {
            this.#requestFlush();
            return;
        }
        this.#resolveIdleIfReady();
    }

    #isIdle(): boolean {
        return this.#cancelScheduled === null && this.#pendingPayload === null && this.#pendingByKey.size === 0 && !this.#rendering;
    }

    #resolveIdleIfReady(): void {
        if (!this.#isIdle()) {
            return;
        }
        this.#settleIdleWaiters();
    }

    #settleIdleWaiters(): void {
        const waiters = Array.from(this.#idleWaiters);
        this.#idleWaiters.clear();
        for (const waiter of waiters) {
            if (this.#required && this.#failure !== null) waiter.reject(this.#failure);
            else waiter.resolve();
        }
    }
}

export { AnimationFrameRenderQueue };
export type { AnimationFrameRenderQueueOptions };
