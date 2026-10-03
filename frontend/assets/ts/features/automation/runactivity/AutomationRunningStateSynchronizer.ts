/* SoAI - Global automation running state reconciliation and recovery [frontend/assets/ts/features/automation/runactivity/AutomationRunningStateSynchronizer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import { APIError } from '@core/apiError.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { createAbortError, isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import { parseRunStatusFromRecord } from '@features/automation/runactivity/parsing.ts';
import { AutomationRunActivityState } from '@features/automation/runactivity/state.ts';
import type { AutomationRunActivitySnapshot } from '@features/automation/runactivity/types.ts';

const log = createModuleLogger('AutomationRunningStateSynchronizer', { defaultLevel: 'warn' });
const MAXIMUM_ATTEMPTS = 5;
type AutomationRunActivityApi = {
    automations: {
        runs: Pick<ApiClient['automations']['runs'], 'get' | 'listActive'>;
    };
};

class AutomationRunningStateSynchronizer {
    readonly #api: AutomationRunActivityApi;
    readonly #notify: () => void;
    readonly #state = new AutomationRunActivityState();
    readonly #resources = new ResourceTracker();
    readonly #events = new SequenceToken();
    readonly #pending = new Map<string, number>();
    readonly #notFound = new Set<string>();
    #scope = new AbortController();
    #waiters: Array<{ resolve: () => void; reject: (error: Error) => void }> = [];
    #worker: Promise<void> | null = null;
    #resyncRequested = false;
    #failures = 0;
    #retryTimer: number | null = null;
    #connected = true;
    #authenticated = false;

    constructor(api: AutomationRunActivityApi, notify: () => void) {
        this.#api = api;
        this.#notify = notify;
    }

    getSnapshot(): AutomationRunActivitySnapshot {
        return this.#state.getSnapshot();
    }

    isConnected(): boolean {
        return this.#connected;
    }

    synchronize(): Promise<void> {
        if (!this.#authenticated || this.#scope.signal.aborted) return Promise.reject(createAbortError());
        this.#failures = 0;
        this.#clearRetry();
        this.#resyncRequested = true;
        this.#events.invalidate();
        if (!this.#connected) return Promise.reject(createAbortError());
        const deferred = createDeferred<void>();
        this.#waiters.push(deferred);
        this.#start();
        return deferred.promise;
    }

    setAuthenticated(authenticated: boolean): void {
        this.#scope.abort();
        this.#scope = new AbortController();
        this.#events.invalidate();
        this.#clearRetry();
        this.#settle(createAbortError());
        this.#authenticated = authenticated;
        this.#pending.clear();
        this.#notFound.clear();
        this.#resyncRequested = false;
        this.#failures = 0;
        this.#state.reset();
        this.#notify();
    }

    noteRunChanged(runId: string): void {
        if (!this.#authenticated || this.#notFound.has(runId)) return;
        this.#pending.set(runId, this.#events.next());
        this.#state.markStale();
        this.#notify();
        this.#start();
    }

    noteConnectionLost(): void {
        this.#connected = false;
        this.#scope.abort();
        this.#settle(createAbortError());
        this.#scope = new AbortController();
        this.#events.invalidate();
        this.#resyncRequested = true;
        this.#state.markStale();
        this.#notify();
    }

    noteConnectionRestored(): boolean {
        const interrupted = !this.#connected;
        this.#connected = true;
        return interrupted;
    }

    dispose(): void {
        this.setAuthenticated(false);
        this.#scope.abort();
    }

    #start(): void {
        if (this.#worker !== null || !this.#authenticated || !this.#connected || this.#scope.signal.aborted || this.#retryTimer !== null || this.#failures >= MAXIMUM_ATTEMPTS) return;
        const signal = this.#scope.signal;
        this.#worker = this.#drain(signal).finally(() => {
            this.#worker = null;
            if (this.#resyncRequested || this.#pending.size > 0) this.#start();
        });
    }

    async #drain(signal: AbortSignal): Promise<void> {
        try {
            while (!signal.aborted && this.#connected && this.#authenticated) {
                if (this.#resyncRequested) {
                    const generation = this.#events.value;
                    const records = await raceWithAbortSignal(this.#api.automations.runs.listActive(signal), signal);
                    const parsed = records.map(parseRunStatusFromRecord);
                    if (signal.aborted || !this.#events.isActive(generation)) continue;
                    this.#state.reset();
                    parsed.forEach((record) => this.#state.applyRunUpdate(record));
                    this.#state.markInitialized();
                    this.#notFound.clear();
                    this.#pending.clear();
                    this.#resyncRequested = false;
                    this.#failures = 0;
                    this.#notify();
                    this.#settle();
                    continue;
                }
                const next = this.#pending.entries().next();
                if (next.done) return;
                const [runId, generation] = next.value;
                try {
                    const record = await raceWithAbortSignal(this.#api.automations.runs.get(runId, signal), signal);
                    const parsed = parseRunStatusFromRecord(record);
                    if (signal.aborted || this.#resyncRequested || this.#pending.get(runId) !== generation) continue;
                    this.#state.applyRunUpdate(parsed);
                    this.#notFound.delete(runId);
                } catch (error) {
                    const runtimeError = ensureError(error);
                    if (!(runtimeError instanceof APIError && runtimeError.status === 404)) throw runtimeError;
                    if (signal.aborted || this.#resyncRequested || this.#pending.get(runId) !== generation) continue;
                    this.#state.removeRun(runId);
                    this.#notFound.add(runId);
                }
                this.#pending.delete(runId);
                this.#failures = 0;
                if (this.#pending.size === 0) this.#state.markInitialized();
                this.#notify();
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            if (signal.aborted || isAbortError(runtimeError)) return;
            this.#state.markStale();
            this.#notify();
            this.#settle(runtimeError);
            this.#failures += 1;
            if (this.#failures >= MAXIMUM_ATTEMPTS) {
                log('warn', 'Automation running state recovery exhausted', runtimeError);
                return;
            }
            this.#retryTimer = this.#resources.setTimeout(
                () => {
                    this.#retryTimer = null;
                    this.#start();
                },
                Math.min(1000 * 2 ** (this.#failures - 1), 30000)
            );
        }
    }

    #clearRetry(): void {
        if (this.#retryTimer !== null) this.#resources.clearTimeout(this.#retryTimer);
        this.#retryTimer = null;
    }

    #settle(error: Error | null = null): void {
        this.#waiters.splice(0).forEach((waiter) => (error === null ? waiter.resolve() : waiter.reject(error)));
    }
}

export { AutomationRunningStateSynchronizer };
export type { AutomationRunActivityApi };
