/* SoAI - Collection shell, readiness, loading, and streaming lifecycle ownership [frontend/assets/ts/core/routing/pages/collections/pagelifecyclemanager/CollectionPageLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { coerceErrorMessage } from '@core/errors/coerce.ts';
import type { CollectionLifecycleDependencies, LayoutElements, LifecycleOptions, WaitOptions } from '@core/routing/pages/collections/pagelifecyclemanager/contracts.ts';
import type { WithLoadingOptions } from '@core/routing/pages/collections/resource/types.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

class CollectionPageLifecycle {
    readonly #dependencies: CollectionLifecycleDependencies;
    readonly #checkerboardSelector: string | null;
    readonly #waitAttempts: number;
    #disposed = false;

    constructor(dependencies: CollectionLifecycleDependencies, options: LifecycleOptions = {}) {
        this.#dependencies = dependencies;
        this.#checkerboardSelector = options.checkerboardSelector || null;
        this.#waitAttempts = isFiniteNumber(options.waitAttempts) ? Math.max(0, options.waitAttempts) : 10;
    }

    dispose(): void {
        this.#disposed = true;
    }

    async render(): Promise<TrustedHtml> {
        this.#ensureActive();
        return this.#dependencies.layout.render();
    }

    async ensureLayoutReady(options: WaitOptions = {}): Promise<LayoutElements> {
        this.#ensureActive();
        const waitOptions = this.#waitOptions(options);
        try {
            return await this.#dependencies.layout.ensureLayoutReady(waitOptions);
        } catch (error) {
            throw new Error(`CollectionPageLifecycle.ensureLayoutReady() failed for page ${this.#dependencies.pageId}: ${coerceErrorMessage(error)}`);
        }
    }

    async initializeShell(callback: ((layout: LayoutElements) => Promise<void> | void) | null, options: WaitOptions = {}): Promise<LayoutElements> {
        const waitOptions = this.#waitOptions(options);
        let layout: LayoutElements;
        try {
            layout = await this.ensureLayoutReady(waitOptions);
        } catch (error) {
            throw new Error(`initializeShell failed for page ${this.#dependencies.pageId}: layout not ready. This usually means render() did not produce the expected grid container. ${coerceErrorMessage(error)}`);
        }
        if (waitOptions.signal?.aborted || this.#dependencies.pageLifecycle.isDestroyed) return layout;
        if (this.#checkerboardSelector) {
            try {
                await this.#dependencies.layout.enableGridCheckerboard(this.#checkerboardSelector, waitOptions);
            } catch (error) {
                throw new Error(`Failed to enable checkerboard for page ${this.#dependencies.pageId}: ${coerceErrorMessage(error)}`);
            }
        }
        if (waitOptions.signal?.aborted || this.#dependencies.pageLifecycle.isDestroyed) return layout;
        if (callback) {
            try {
                await callback(layout);
            } catch (error) {
                throw new Error(`initializeShell callback failed for page ${this.#dependencies.pageId}: ${coerceErrorMessage(error)}`);
            }
        }
        return layout;
    }

    async startLiveUpdates(options: WaitOptions = {}): Promise<void> {
        this.#ensureActive();
        const waitOptions = this.#waitOptions(options);
        if (waitOptions.signal?.aborted || this.#dependencies.pageLifecycle.isDestroyed) return;
        await this.#dependencies.collections.ensureStream({ allowDiscovery: options.allowDiscovery !== false, signal: waitOptions.signal });
    }

    async withLoading<T extends JsonValue | null>(task: () => Promise<T>, options: WithLoadingOptions<T>): Promise<T> {
        this.#ensureActive();
        const result = await this.#dependencies.layout.withLoading(task, options);
        if (result === null) throw new Error(`Collection runtime withLoading() returned null for page ${this.#dependencies.pageId}`);
        return result;
    }

    getLoadingTargetElement(): HTMLElement {
        this.#ensureActive();
        return this.#dependencies.layout.getLoadingTargetElement();
    }

    #waitOptions(options: WaitOptions): { attempts: number; signal: AbortSignal | undefined } {
        const attempts = isFiniteNumber(options.attempts) ? Math.max(0, options.attempts) : this.#waitAttempts;
        return { attempts, signal: options.signal ?? this.#dependencies.pageLifecycle.signal() ?? undefined };
    }

    #ensureActive(): void {
        if (this.#disposed) throw new Error(`CollectionPageLifecycle for page ${this.#dependencies.pageId} has been disposed`);
    }
}

export { CollectionPageLifecycle };
