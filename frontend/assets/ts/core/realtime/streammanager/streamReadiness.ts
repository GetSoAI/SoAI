/* SoAI - Frontend stream readiness lifecycle ownership [frontend/assets/ts/core/realtime/streammanager/streamReadiness.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isWizardSetupNeededSnapshot } from '@core/auth/wizardStatus.ts';
import { ensureBackendReady } from '@core/backendReady.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { LifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { getAutoResourceState } from '@core/realtime/streammanager/autoresources/state.ts';
import { emitStreamEvent } from '@core/realtime/streammanager/internals.ts';
import { awaitDeferredReadyState, createDeferredReadyState, failDeferredReadyState, resetDeferredReadyState, settleDeferredReadyState, type DeferredReadyState } from '@core/realtime/streammanager/state.ts';
import type { AuthManagerContract, DeferredReadyOptions } from '@core/realtime/streammanager/types.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isFunction } from '@core/typeGuards.ts';

const MODULE = 'StreamManager';

interface StreamReadinessRuntime {
    auth: AuthManagerContract | null;
    tracker: ResourceTracker;
    initializeTransport: () => void;
}

class StreamReadiness {
    #auth: AuthManagerContract | null;
    #tracker: ResourceTracker;
    #initializeTransport: () => void;
    #ready = false;
    #readyTasks = new Map<string, Promise<void>>();
    #baseUrlTasks = new Map<boolean, Promise<string>>();
    #deferredTaskKeys = new Map<DeferredReadyState, string>();
    #generation = 0;
    #resetAbort = new AbortController();
    #disposed = false;
    #clearDeferredTimer = (timerId: number): void => {
        this.#tracker.clearTimeout(timerId);
    };

    constructor(runtime: StreamReadinessRuntime) {
        this.#auth = runtime.auth;
        this.#tracker = runtime.tracker;
        this.#initializeTransport = runtime.initializeTransport;
    }

    get ready(): boolean {
        return this.#ready;
    }

    get generation(): number {
        return this.#generation;
    }

    get resetSignal(): AbortSignal {
        return this.#resetAbort.signal;
    }

    shouldDefer(): boolean {
        const snapshot = this.#auth && isFunction(this.#auth.getWizardStatusSnapshot) ? this.#auth.getWizardStatusSnapshot() : null;
        return isWizardSetupNeededSnapshot(snapshot) || this.#auth?.isAuthenticated !== true;
    }

    resetDeferred(): void {
        for (const [state, taskKey] of [...this.#deferredTaskKeys]) {
            this.#readyTasks.delete(taskKey);
            this.#resetDeferredState(state);
        }
    }

    settleDeferred(): void {
        for (const state of [...this.#deferredTaskKeys.keys()]) this.#settleDeferredState(state);
    }

    failDeferred(error: Error): void {
        for (const state of [...this.#deferredTaskKeys.keys()]) this.#failDeferredState(state, error);
    }

    async ensureApi(options: { allowDiscovery?: boolean; signal?: AbortSignal | null } = {}): Promise<string> {
        this.#requireActive();
        if (options.signal?.aborted) throw createAbortError();
        const allowDiscovery = options.allowDiscovery !== false;
        let task = this.#baseUrlTasks.get(allowDiscovery);
        if (!task) {
            const resetSignal = this.#resetAbort.signal;
            let ownedTask!: Promise<string>;
            ownedTask = raceWithAbortSignal(
                ensureBackendReady({ allowDiscovery, signal: resetSignal }).then(({ baseUrl }) => baseUrl),
                resetSignal
            ).finally(() => {
                if (this.#baseUrlTasks.get(allowDiscovery) === ownedTask) this.#baseUrlTasks.delete(allowDiscovery);
            });
            this.#baseUrlTasks.set(allowDiscovery, ownedTask);
            task = ownedTask;
        }
        return options.signal ? raceWithAbortSignal(task, options.signal) : task;
    }

    async #initialize(taskKey: string, options: DeferredReadyOptions & { allowDiscovery?: boolean } = {}): Promise<void> {
        const generation = this.#generation;
        const signal = this.#resetAbort.signal;
        const deferredState = createDeferredReadyState();
        this.#deferredTaskKeys.set(deferredState, taskKey);
        const deferred = awaitDeferredReadyState(
            deferredState,
            {
                shouldDeferInitialization: () => this.shouldDefer(),
                setTimer: (callback, timeoutMs) => this.#tracker.setTimeout(callback, timeoutMs),
                clearTimer: this.#clearDeferredTimer,
                onTimeout: () => {
                    if (generation === this.#generation) this.#failDeferredState(deferredState, new Error('Init timeout'));
                }
            },
            options
        );
        if (deferred === null) this.#releaseDeferredStateOwnership(deferredState);
        return await (async () => {
            try {
                if (deferred) await raceWithAbortSignal(deferred, signal);
                await raceWithAbortSignal(this.ensureApi({ allowDiscovery: options.allowDiscovery !== false, signal }), signal);
                this.#initializeTransport();
                this.#ready = true;
                this.#settleDeferredState(deferredState);
            } catch (error) {
                const runtimeError = ensureError(error);
                if (generation === this.#generation) this.#failDeferredState(deferredState, runtimeError);
                throw runtimeError;
            } finally {
                this.#resetDeferredState(deferredState);
            }
        })();
    }

    async #ensure(options: DeferredReadyOptions & { allowDiscovery?: boolean; signal?: AbortSignal | undefined }): Promise<void> {
        this.#requireActive();
        if (this.#ready) {
            emitStreamEvent('ensureReady:cached', { autoResources: getAutoResourceState().status });
            return;
        }
        const allowDiscovery = options.allowDiscovery !== false;
        const timeoutKey = typeof options.deferTimeoutMs === 'number' ? String(options.deferTimeoutMs) : 'default';
        const taskKey = `${allowDiscovery ? 'discovery' : 'configured'}:${timeoutKey}`;
        const existingTask = this.#readyTasks.get(taskKey);
        if (existingTask) return options.signal ? raceWithAbortSignal(existingTask, options.signal) : existingTask;
        const context = { allowDiscovery, autoResources: getAutoResourceState().status };
        const initializationOptions: DeferredReadyOptions & { allowDiscovery?: boolean } = {};
        if (typeof options.deferTimeoutMs === 'number') initializationOptions.deferTimeoutMs = options.deferTimeoutMs;
        if (typeof options.allowDiscovery === 'boolean') initializationOptions.allowDiscovery = options.allowDiscovery;
        emitStreamEvent('ensureReady:start', context);
        const task = this.#initialize(taskKey, initializationOptions)
            .then(() => emitStreamEvent('ensureReady:complete', context))
            .catch((error) => {
                const runtimeError = ensureError(error);
                emitStreamEvent('ensureReady:error', { ...context, message: runtimeError.message }, 'error');
                throw runtimeError;
            })
            .finally(() => {
                if (this.#readyTasks.get(taskKey) === task) this.#readyTasks.delete(taskKey);
            });
        this.#readyTasks.set(taskKey, task);
        return options.signal ? raceWithAbortSignal(task, options.signal) : task;
    }

    ensure(options: DeferredReadyOptions & { allowDiscovery?: boolean; throwOnError?: boolean; signal?: AbortSignal | undefined } = {}): Promise<void> {
        if (this.#disposed) return Promise.reject(new LifecycleCancellationError('Stream readiness is disposed', 'stream-readiness-disposed'));
        if (options.signal?.aborted) {
            const error = createAbortError();
            if (options.throwOnError === false) {
                errorHandler.debug(MODULE, 'ensureReady suppressed abort', error);
                return Promise.resolve();
            }
            return Promise.reject(error);
        }
        const task = this.#ensure(options);
        if (options.throwOnError !== false) return task;
        return task.catch((error) => errorHandler.debug(MODULE, 'ensureReady suppressed error', ensureError(error)));
    }

    reset(): void {
        this.#requireActive();
        this.#generation += 1;
        this.#resetAbort.abort();
        this.#resetAbort = new AbortController();
        this.#ready = false;
        this.#baseUrlTasks.clear();
        this.#readyTasks.clear();
        this.failDeferred(new LifecycleCancellationError('Stream manager reset during lifecycle transition', 'stream-manager-reset'));
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#generation += 1;
        this.#resetAbort.abort();
        this.#ready = false;
        this.#baseUrlTasks.clear();
        this.#readyTasks.clear();
        this.failDeferred(new LifecycleCancellationError('Stream manager disposed during lifecycle transition', 'stream-manager-dispose'));
    }

    #requireActive(): void {
        if (this.#disposed) throw new LifecycleCancellationError('Stream readiness is disposed', 'stream-readiness-disposed');
    }

    #resetDeferredState(state: DeferredReadyState): void {
        resetDeferredReadyState(state, this.#clearDeferredTimer);
        this.#releaseDeferredStateOwnership(state);
    }

    #releaseDeferredStateOwnership(state: DeferredReadyState): void {
        this.#deferredTaskKeys.delete(state);
    }

    #settleDeferredState(state: DeferredReadyState): void {
        settleDeferredReadyState(state, () => this.#resetDeferredState(state));
    }

    #failDeferredState(state: DeferredReadyState, error: Error): void {
        failDeferredReadyState(state, error, () => this.#resetDeferredState(state));
    }
}

export { StreamReadiness };
