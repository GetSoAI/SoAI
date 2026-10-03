/* SoAI - Automation page data owner serializing refresh, realtime, and staleness [frontend/assets/ts/pages/automation/controllers/AutomationPageDataController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { createAbortError, isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { resolveBufferedAutomationWindow } from '@pages/automation/controllers/automationWindow.ts';
import { applyAutomationRunRecord, loadBufferedWindowZones } from '@pages/automation/controllers/AutomationWindowDataDomain.ts';
import type { AutomationDataService } from '@features/automation/public.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';

const RUN_RETRY_MAX_ATTEMPTS = 5;
const RUN_RETRY_BASE_DELAY_MS = 1000;
const RUN_RETRY_MAX_DELAY_MS = 30000;

interface AutomationPageDataStatus {
    stale: boolean;
    recoveryRequired: boolean;
    lastSyncedAtMs: number | null;
}

interface AutomationPageDataControllerDependencies {
    dataService: AutomationDataService;
    getState: () => AutomationPageState;
    setState: (next: AutomationPageState) => void;
    queueRender: () => void;
    isDestroyed: () => boolean;
    setTimeout: (callback: () => void, delay: number) => number | null;
    clearTimer: (timerId: number | null | undefined) => void;
}

interface RefreshWaiter {
    resolve: () => void;
    reject: (error: Error) => void;
}

class AutomationPageDataController {
    readonly #dependencies: AutomationPageDataControllerDependencies;
    readonly #pendingRuns = new Map<string, number>();
    readonly #lifecycle = new AbortController();
    readonly #resourceGeneration = new SequenceToken();
    readonly #connectionGeneration = new SequenceToken();
    readonly #windowGeneration = new SequenceToken();
    #refreshWaiters: RefreshWaiter[] = [];
    #refreshRequested = false;
    #worker: Promise<void> | null = null;
    #eventGeneration = 0;
    #windowSignature = '';
    #stale = false;
    #recoveryRequired = false;
    #lastSyncedAtMs: number | null = null;
    #runFailures = 0;
    #retryTimer: number | null = null;
    #connected = true;

    constructor(dependencies: AutomationPageDataControllerDependencies) {
        this.#dependencies = dependencies;
    }

    getStatus(): AutomationPageDataStatus {
        return { stale: this.#stale, recoveryRequired: this.#recoveryRequired, lastSyncedAtMs: this.#lastSyncedAtMs };
    }

    refresh(): Promise<void> {
        if (this.#isDisposed()) return Promise.reject(createAbortError());
        this.#resourceGeneration.invalidate();
        const deferred = createDeferred<void>();
        this.#refreshWaiters.push(deferred);
        this.#refreshRequested = true;
        this.#ensureWorker();
        return deferred.promise;
    }

    requestRefresh(): void {
        terminateHandledPromise(this.refresh());
    }

    retry(): Promise<void> {
        this.#clearRetryTimer();
        this.#runFailures = 0;
        return this.refresh();
    }

    noteWindowChanged(): void {
        if (this.#isDisposed()) return;
        this.#windowGeneration.invalidate();
        this.#resourceGeneration.invalidate();
        this.#setStale(true);
        if (this.#worker !== null) this.#refreshRequested = true;
    }

    noteRunChanged(runId: string): void {
        if (this.#isDisposed()) return;
        this.#resourceGeneration.invalidate();
        this.#eventGeneration += 1;
        this.#pendingRuns.set(runId, this.#eventGeneration);
        this.#setStale(true);
        this.#ensureWorker();
    }

    noteDefinitionsChanged(): void {
        if (this.#isDisposed()) return;
        this.#eventGeneration += 1;
        this.#setStale(true);
        this.requestRefresh();
    }

    noteConnectionLost(): void {
        if (this.#isDisposed()) return;
        this.#connected = false;
        this.#connectionGeneration.invalidate();
        this.#setStale(true);
    }

    noteConnectionRestored(): void {
        if (this.#isDisposed()) return;
        const interrupted = !this.#connected;
        this.#connected = true;
        if (interrupted || this.#stale) {
            this.#connectionGeneration.invalidate();
            this.retry().catch((error) => errorHandler.debug('AutomationPageDataController', 'Automation resync after reconnect failed', ensureError(error)));
        }
    }

    dispose(): void {
        this.#lifecycle.abort();
        this.#clearRetryTimer();
        this.#pendingRuns.clear();
        this.#refreshRequested = false;
        this.#settleRefresh(createAbortError());
    }

    #isDisposed(): boolean {
        return this.#lifecycle.signal.aborted || this.#dependencies.isDestroyed();
    }

    #settleRefresh(error: Error | null = null): void {
        this.#refreshWaiters.splice(0).forEach((waiter) => (error === null ? waiter.resolve() : waiter.reject(error)));
    }

    #ensureWorker(): void {
        if (this.#worker !== null || this.#isDisposed()) {
            return;
        }
        this.#worker = this.#work().finally(() => {
            this.#worker = null;
            if (!this.#isDisposed() && (this.#refreshRequested || (this.#pendingRuns.size > 0 && this.#retryTimer === null && this.#runFailures < RUN_RETRY_MAX_ATTEMPTS))) {
                this.#ensureWorker();
            }
        });
    }

    async #work(): Promise<void> {
        while (!this.#isDisposed()) {
            if (this.#refreshRequested) {
                await this.#runRefreshAttempt();
                continue;
            }
            const next = this.#retryTimer === null && this.#runFailures < RUN_RETRY_MAX_ATTEMPTS ? this.#pendingRuns.entries().next() : null;
            if (!next || next.done === true) {
                return;
            }
            const [runId, generation] = next.value;
            if (!(await this.#applyRun(runId, generation))) {
                this.#scheduleRunRetry();
                return;
            }
        }
    }

    async #runRefreshAttempt(): Promise<void> {
        this.#refreshRequested = false;
        const startGeneration = this.#eventGeneration;
        const resourceGeneration = this.#resourceGeneration.value;
        const connectionGeneration = this.#connectionGeneration.value;
        const windowGeneration = this.#windowGeneration.value;
        const requested = this.#dependencies.getState();
        const bufferedWindow = resolveBufferedAutomationWindow(requested);
        try {
            const signal = this.#lifecycle.signal;
            const [automationPage, zones] = await raceWithAbortSignal(Promise.all([this.#dependencies.dataService.listAutomations(requested.automationRegistryLimit, requested.automationRegistryOffset, signal), loadBufferedWindowZones(this.#dependencies.dataService, bufferedWindow.fromUtcMs, bufferedWindow.toUtcMs, signal)]), signal);
            if (this.#isDisposed()) return;
            const current = this.#dependencies.getState();
            if (!this.#resourceGeneration.isActive(resourceGeneration) || !this.#connectionGeneration.isActive(connectionGeneration) || !this.#windowGeneration.isActive(windowGeneration) || resolveBufferedAutomationWindow(current).signature !== bufferedWindow.signature || current.automationRegistryOffset !== requested.automationRegistryOffset || current.automationRegistryLimit !== requested.automationRegistryLimit) {
                this.#refreshRequested = true;
                return;
            }
            const recoveredOffset = automationPage.automations.length === 0 && automationPage.offset > 0 ? Math.max(0, automationPage.offset - automationPage.limit) : null;
            this.#dependencies.setState({
                ...current,
                automations: automationPage.automations,
                automationRegistryLimit: automationPage.limit,
                automationRegistryOffset: recoveredOffset ?? automationPage.offset,
                automationRegistryHasMore: automationPage.hasMore,
                zones
            });
            this.#windowSignature = bufferedWindow.signature;
            for (const [runId, generation] of this.#pendingRuns) {
                if (generation <= startGeneration) this.#pendingRuns.delete(runId);
            }
            this.#clearRetryTimer();
            this.#runFailures = 0;
            this.#lastSyncedAtMs = Date.now();
            this.#setRecoveryRequired(false);
            this.#setStale(!this.#connected);
            if (recoveredOffset !== null) {
                this.#refreshRequested = true;
                return;
            }
            this.#dependencies.queueRender();
            this.#settleRefresh();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (this.#isDisposed()) {
                this.#settleRefresh(createAbortError());
                return;
            }
            if (!this.#resourceGeneration.isActive(resourceGeneration) || !this.#connectionGeneration.isActive(connectionGeneration) || !this.#windowGeneration.isActive(windowGeneration)) {
                this.#refreshRequested = true;
                return;
            }
            this.#setStale(true);
            this.#setRecoveryRequired(true);
            this.#settleRefresh(runtimeError);
        }
    }

    async #applyRun(runId: string, generation: number): Promise<boolean> {
        const resourceGeneration = this.#resourceGeneration.value;
        const connectionGeneration = this.#connectionGeneration.value;
        const windowGeneration = this.#windowGeneration.value;
        const requested = this.#dependencies.getState();
        const windowSignature = resolveBufferedAutomationWindow(requested).signature;
        try {
            const signal = this.#lifecycle.signal;
            const record = await raceWithAbortSignal(this.#dependencies.dataService.getRun(runId, signal), signal);
            const summaries = await raceWithAbortSignal(this.#dependencies.dataService.listAutomations(requested.automationRegistryLimit, requested.automationRegistryOffset, signal), signal);
            if (this.#isDisposed() || this.#pendingRuns.get(runId) !== generation) {
                return true;
            }
            const state = this.#dependencies.getState();
            const bufferedWindow = resolveBufferedAutomationWindow(state);
            if (!this.#resourceGeneration.isActive(resourceGeneration) || !this.#connectionGeneration.isActive(connectionGeneration) || !this.#windowGeneration.isActive(windowGeneration) || windowSignature !== bufferedWindow.signature || state.automationRegistryOffset !== requested.automationRegistryOffset || state.automationRegistryLimit !== requested.automationRegistryLimit || this.#windowSignature !== bufferedWindow.signature) {
                this.#refreshRequested = true;
                return true;
            }
            this.#pendingRuns.delete(runId);
            const result = applyAutomationRunRecord(state, bufferedWindow, record);
            if (result.type === 'needs-refresh') {
                this.#refreshRequested = true;
            } else {
                this.#dependencies.setState({ ...(result.type === 'applied' ? result.state : state), automations: summaries.automations });
                this.#dependencies.queueRender();
            }
            this.#runFailures = 0;
            if (this.#pendingRuns.size === 0) {
                const needsReconciliation = this.#recoveryRequired || this.#refreshRequested;
                if (!needsReconciliation) this.#lastSyncedAtMs = Date.now();
                this.#setStale(!this.#connected || needsReconciliation);
            }
            return true;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (this.#isDisposed() || isAbortError(runtimeError)) return true;
            if (runtimeError instanceof APIError && runtimeError.status === 404) {
                if (this.#pendingRuns.get(runId) === generation) this.#pendingRuns.delete(runId);
                this.#refreshRequested = true;
                return true;
            }
            if (this.#runFailures + 1 >= RUN_RETRY_MAX_ATTEMPTS) errorHandler.warn('AutomationPageDataController', 'Automation run recovery exhausted', runtimeError, { context: { runId } });
            return false;
        }
    }

    #scheduleRunRetry(): void {
        this.#setStale(true);
        this.#runFailures += 1;
        if (this.#runFailures >= RUN_RETRY_MAX_ATTEMPTS) {
            this.#setRecoveryRequired(true);
            return;
        }
        const delay = Math.min(RUN_RETRY_BASE_DELAY_MS * 2 ** (this.#runFailures - 1), RUN_RETRY_MAX_DELAY_MS);
        this.#retryTimer = this.#dependencies.setTimeout(() => {
            this.#retryTimer = null;
            this.#ensureWorker();
        }, delay);
    }

    #clearRetryTimer(): void {
        this.#dependencies.clearTimer(this.#retryTimer);
        this.#retryTimer = null;
    }

    #setStale(stale: boolean): void {
        if (this.#stale === stale) {
            return;
        }
        this.#stale = stale;
        this.#dependencies.queueRender();
    }

    #setRecoveryRequired(required: boolean): void {
        if (this.#recoveryRequired === required) return;
        this.#recoveryRequired = required;
        this.#dependencies.queueRender();
    }
}

export { AutomationPageDataController };
export type { AutomationPageDataStatus };
