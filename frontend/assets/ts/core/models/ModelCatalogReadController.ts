/* SoAI - Shared model catalog read and observation ownership [frontend/assets/ts/core/models/ModelCatalogReadController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { TIMEOUTS } from '@core/constants.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { ModelCatalogObservation, ModelCatalogSubscriber } from '@core/models/modelCatalogObservation.ts';
import { LifecycleScope, type LifecycleRun } from '@core/lifecycle/lifecycleScope.ts';
import { isPresentationOwnerCurrent } from '@core/presentationOwner.ts';
import type { PresentationOwner } from '@core/routing/router/types.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { monotonicMs } from '@core/time/clock.ts';

interface ModelCatalogReadDependencies<T> {
    readonly owner: PresentationOwner;
    readonly signal?: AbortSignal;
    readonly subscribeCatalog: ModelCatalogSubscriber;
    readCatalog(signal: AbortSignal, timeoutMs: number): Promise<T>;
    applyCatalog(catalog: T | null): void;
    reportFailure(error: Error): void;
}

class ModelCatalogReadController<T> {
    readonly #dependencies: ModelCatalogReadDependencies<T>;
    readonly #lifetime = new LifecycleScope();
    readonly #reads = new SequenceToken();
    #session: LifecycleRun | null = null;
    #task: Promise<boolean> | null = null;
    #unsubscribe: (() => void) | null = null;
    #releaseFailure: { error: Error; release: () => void } | null = null;
    #fresh = false;
    #observedType: ModelCatalogObservation['type'] | null = null;

    constructor(dependencies: ModelCatalogReadDependencies<T>) {
        this.#dependencies = dependencies;
    }

    start(): void {
        if (this.#releaseFailure) throw this.#releaseFailure.error;
        const unsubscribe = this.#unsubscribe;
        this.#unsubscribe = null;
        this.#fresh = false;
        this.#observedType = null;
        this.#task = null;
        const session = this.#lifetime.begin('model-catalog-replaced');
        this.#release(unsubscribe);
        if (!this.#lifetime.isCurrent(session)) return;
        this.#session = session;
        const release = this.#dependencies.subscribeCatalog((observation) => {
            if (!this.#isCurrent(session)) return;
            this.#reads.invalidate();
            this.#fresh = false;
            this.#observedType = observation.type;
            this.#dependencies.applyCatalog(null);
            if (observation.type === 'current' && this.#isCurrent(session)) {
                void this.ensureReady().catch((error) => {
                    if (this.#isCurrent(session)) errorHandler.error('ModelCatalogReadController', 'Model catalog observation failed', ensureError(error));
                });
            }
        });
        if (this.#isCurrent(session)) this.#unsubscribe = release;
        else this.#release(release);
    }

    stop(): void {
        const unsubscribe = this.#unsubscribe;
        this.#unsubscribe = null;
        this.#session = null;
        this.#task = null;
        this.#fresh = false;
        this.#lifetime.abort('model-catalog-closed');
        this.#release(unsubscribe);
        if (this.#releaseFailure) throw this.#releaseFailure.error;
    }

    async ensureReady(): Promise<boolean> {
        const session = this.#session;
        if (!session || !this.#isCurrent(session)) return false;
        if (this.#observedType !== null && this.#observedType !== 'current') return false;
        if (this.#fresh) return true;
        if (this.#task) return await this.#task;
        const completion = createDeferred<boolean>();
        this.#task = completion.promise;
        const isCurrent = (): boolean => this.#isCurrent(session) && this.#task === completion.promise;
        const finish = (ready: boolean): void => {
            if (this.#task === completion.promise) this.#task = null;
            completion.resolve(ready);
        };
        void this.#read(session, isCurrent, finish).catch((error) => {
            if (this.#task === completion.promise) this.#task = null;
            completion.reject(ensureError(error));
        });
        return await completion.promise;
    }

    isReady(): boolean {
        return this.#session !== null && this.#isCurrent(this.#session) && this.#fresh;
    }

    #isCurrent(session: LifecycleRun): boolean {
        return !this.#dependencies.signal?.aborted && this.#releaseFailure === null && this.#lifetime.isCurrent(session) && isPresentationOwnerCurrent(this.#dependencies.owner);
    }

    async #read(session: LifecycleRun, isCurrent: () => boolean, finish: (ready: boolean) => void): Promise<void> {
        const deadline = monotonicMs() + TIMEOUTS.API_REQUEST;
        for (let attempt = 0; attempt < 2; attempt += 1) {
            if (!isCurrent()) return finish(false);
            if (this.#observedType !== null && this.#observedType !== 'current') return finish(false);
            const token = this.#reads.next();
            const remainingMs = deadline - monotonicMs();
            if (remainingMs <= 0) break;
            try {
                const catalog = await this.#dependencies.readCatalog(session.signal, remainingMs);
                if (!isCurrent()) return finish(false);
                if (monotonicMs() >= deadline) break;
                if (!this.#reads.isActive(token)) continue;
                this.#fresh = true;
                this.#dependencies.applyCatalog(catalog);
                if (!isCurrent()) return finish(false);
                if (this.#reads.isActive(token) && this.#fresh) return finish(true);
            } catch (error) {
                if (!isCurrent() || isAbortError(error)) return finish(false);
                if (!this.#reads.isActive(token)) continue;
                this.#fresh = false;
                this.#dependencies.reportFailure(ensureError(error));
                return finish(false);
            }
        }
        if (isCurrent()) this.#dependencies.reportFailure(new Error('The model catalog could not be reconciled within its read budget.'));
        finish(false);
    }

    #release(unsubscribe: (() => void) | null): void {
        if (!unsubscribe) return;
        try {
            unsubscribe();
        } catch (error) {
            this.#releaseFailure = { error: ensureError(error), release: unsubscribe };
            throw this.#releaseFailure.error;
        }
    }
}

export { ModelCatalogReadController };
