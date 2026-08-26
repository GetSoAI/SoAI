/* SoAI - Coalesced animation-frame render queue [frontend/assets/ts/core/animations/renderQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isThenable } from '@core/typeGuards.ts';

interface AnimationFrameRenderQueueOptions<TPayload> {
    label: string;
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
    readonly #render: ((payload: TPayload) => void | Promise<void>) | undefined;
    readonly #renderBatch: ((payloads: readonly TPayload[]) => void | Promise<void>) | undefined;
    readonly #merge: (previous: TPayload | null, next: TPayload) => TPayload;
    readonly #keyOf: ((payload: TPayload) => string) | undefined;
    readonly #isDisposed: () => boolean;
    readonly #requestAnimationFrame: (callback: () => void) => number;
    readonly #cancelAnimationFrame: (id: number) => void;
    #frameId: number | null = null;
    #pendingPayload: PendingRenderPayload<TPayload> | null = null;
    #pendingByKey = new Map<string, TPayload>();
    #idleResolvers: Array<() => void> = [];
    #scheduleGeneration = 0;
    #disposed = false;
    #rendering = false;

    constructor(options: AnimationFrameRenderQueueOptions<TPayload>) {
        this.#label = options.label;
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
        if (this.#keyOf) {
            const key = this.#keyOf(payload);
            if (!key) {
                throw new Error('Animation frame render queue keys must not be empty');
            }
            this.#pendingByKey.set(key, this.#merge(this.#pendingByKey.get(key) ?? null, payload));
            if (this.#frameId === null && !this.#rendering) {
                this.#requestFlush();
            }
            return;
        }
        const previous = this.#pendingPayload === null ? null : this.#pendingPayload.value;
        this.#pendingPayload = { value: this.#merge(previous, payload) };
        if (this.#frameId !== null || this.#rendering) {
            return;
        }
        this.#requestFlush();
    }

    cancel(): void {
        this.#scheduleGeneration += 1;
        if (this.#frameId !== null) {
            this.#cancelAnimationFrame(this.#frameId);
            this.#frameId = null;
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
        if (this.#pendingByKey.size === 0 && this.#frameId !== null && !this.#rendering) {
            this.#scheduleGeneration += 1;
            this.#cancelAnimationFrame(this.#frameId);
            this.#frameId = null;
        }
        this.#resolveIdleIfReady();
        return dropped;
    }

    dispose(): void {
        this.#disposed = true;
        this.cancel();
    }

    waitForIdle(): Promise<void> {
        if (this.#disposed || this.#isDisposed()) {
            this.cancel();
        }
        if (this.#isIdle()) {
            return Promise.resolve();
        }
        return new Promise((resolve) => {
            this.#idleResolvers.push(resolve);
        });
    }

    #flush(): void {
        this.#frameId = null;
        if (this.#keyOf) {
            this.#flushKeyed();
            return;
        }
        const pendingPayload = this.#pendingPayload;
        this.#pendingPayload = null;
        if (pendingPayload === null || this.#disposed || this.#isDisposed()) {
            this.#resolveIdleIfReady();
            return;
        }
        this.#rendering = true;
        try {
            const render = this.#render;
            if (!render) {
                throw new Error('Animation frame render callback is unavailable');
            }
            const result = render(pendingPayload.value);
            if (isThenable(result)) {
                void Promise.resolve(result).then(
                    () => this.#finishRender(),
                    (error) => {
                        errorHandler.error(this.#label, 'Animation frame render failed', ensureError(error));
                        this.#finishRender();
                    }
                );
                return;
            }
        } catch (error) {
            errorHandler.error(this.#label, 'Animation frame render failed', ensureError(error));
        }
        this.#finishRender();
    }

    #flushKeyed(): void {
        const pendingPayloads = Array.from(this.#pendingByKey.values());
        this.#pendingByKey.clear();
        if (pendingPayloads.length === 0 || this.#disposed || this.#isDisposed()) {
            this.#resolveIdleIfReady();
            return;
        }
        this.#rendering = true;
        try {
            const renderBatch = this.#renderBatch;
            if (!renderBatch) {
                throw new Error('Keyed animation frame render callback is unavailable');
            }
            const result = renderBatch(pendingPayloads);
            if (isThenable(result)) {
                void Promise.resolve(result).then(
                    () => this.#finishRender(),
                    (error) => {
                        errorHandler.error(this.#label, 'Animation frame render failed', ensureError(error));
                        this.#finishRender();
                    }
                );
                return;
            }
        } catch (error) {
            errorHandler.error(this.#label, 'Animation frame render failed', ensureError(error));
        }
        this.#finishRender();
    }

    #requestFlush(): void {
        const generation = this.#scheduleGeneration + 1;
        this.#scheduleGeneration = generation;
        this.#frameId = this.#requestAnimationFrame(() => {
            if (generation !== this.#scheduleGeneration) {
                return;
            }
            this.#flush();
        });
    }

    #finishRender(): void {
        this.#rendering = false;
        if (this.#disposed || this.#isDisposed()) {
            this.#pendingPayload = null;
            this.#pendingByKey.clear();
            this.#resolveIdleIfReady();
            return;
        }
        if ((this.#pendingPayload !== null || this.#pendingByKey.size > 0) && this.#frameId === null) {
            this.#requestFlush();
            return;
        }
        this.#resolveIdleIfReady();
    }

    #isIdle(): boolean {
        return this.#frameId === null && this.#pendingPayload === null && this.#pendingByKey.size === 0 && !this.#rendering;
    }

    #resolveIdleIfReady(): void {
        if (!this.#isIdle()) {
            return;
        }
        const resolvers = this.#idleResolvers.splice(0);
        for (const resolve of resolvers) {
            resolve();
        }
    }
}

export { AnimationFrameRenderQueue };
export type { AnimationFrameRenderQueueOptions };
