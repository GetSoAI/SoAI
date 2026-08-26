/* SoAI - Automation feature run activity service [frontend/assets/ts/features/automation/runactivity/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import { APIError } from '@core/apiError.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import { isFunction } from '@core/typeGuards.ts';
import { parseRunStatusFromRecord } from '@features/automation/runactivity/parsing.ts';
import { bindAutomationRunActivityRealtimeSubscriptions } from '@features/automation/runactivity/realtimeSubscriptions.ts';
import { AutomationRunActivityState } from '@features/automation/runactivity/state.ts';
import type { AutomationRealtimeUpdate, AutomationRealtimeUpdateListener, AutomationRunActivityListener, AutomationRunActivityServiceContract, AutomationRunActivitySnapshot } from '@features/automation/runactivity/types.ts';

const log = createModuleLogger('AutomationRunActivityService', { defaultLevel: 'warn' });

class AutomationRunActivityService implements AutomationRunActivityServiceContract {
    readonly #api: ApiClient;
    readonly #listeners = new Set<AutomationRunActivityListener>();
    readonly #realtimeListeners = new Set<AutomationRealtimeUpdateListener>();
    readonly #state = new AutomationRunActivityState();
    readonly #authSubscriptions = new ResourceTracker();
    readonly #websocketSubscriptions = new ResourceTracker();
    readonly #pendingRunIds = new Set<string>();
    readonly #notFoundRunIds = new Set<string>();
    readonly #generation = new SequenceToken();
    #initialized = false;
    #initializePromise: Promise<void> | null = null;
    #initialSyncInFlight = false;
    #refreshInFlight = false;
    #refreshRequested = false;

    constructor(api: ApiClient) {
        this.#api = api;
    }

    getSnapshot(): AutomationRunActivitySnapshot {
        return this.#state.getSnapshot();
    }

    subscribe(listener: AutomationRunActivityListener): () => void {
        if (!isFunction(listener)) {
            throw new Error('Automation run activity subscriber must be a function');
        }
        this.#listeners.add(listener);
        try {
            listener(this.getSnapshot());
        } catch (error) {
            log('warn', 'Automation run activity subscriber replay failed', ensureError(error));
        }
        return () => {
            this.#listeners.delete(listener);
        };
    }

    subscribeRealtime(listener: AutomationRealtimeUpdateListener): () => void {
        if (!isFunction(listener)) {
            throw new Error('Automation realtime subscriber must be a function');
        }
        this.#realtimeListeners.add(listener);
        return () => {
            this.#realtimeListeners.delete(listener);
        };
    }

    async initialize(): Promise<void> {
        if (this.#initialized) {
            return;
        }
        if (this.#initializePromise) {
            return this.#initializePromise;
        }
        const generation = this.#generation.next();
        this.#initializePromise = (async (): Promise<void> => {
            try {
                await this.#initialize(generation);
            } catch (error) {
                await this.destroy();
                throw error;
            } finally {
                this.#initializePromise = null;
            }
        })();
        return this.#initializePromise;
    }

    async destroy(): Promise<void> {
        this.#generation.invalidate();
        this.#clearSubscriptions();
        this.#pendingRunIds.clear();
        this.#notFoundRunIds.clear();
        this.#initialSyncInFlight = false;
        this.#refreshInFlight = false;
        this.#refreshRequested = false;
        this.#initialized = false;
        this.#initializePromise = null;
        this.#state.reset();
        this.#notifyListeners();
    }

    async #initialize(generation: number): Promise<void> {
        this.#bindRealtimeSubscriptions();
        this.#bindAuthSubscriptions();
        if (getAuthManager().isAuthenticated) {
            await this.#primeInitialRunningSet(generation);
        }
        if (!this.#isGenerationActive(generation)) {
            return;
        }
        this.#initialized = true;
        this.#startRefreshDrain(generation);
    }

    #bindRealtimeSubscriptions(): void {
        const scheduleRefreshForRun = (runId: string): void => {
            if (!getAuthManager().isAuthenticated) {
                return;
            }
            if (this.#notFoundRunIds.has(runId)) {
                return;
            }
            this.#pendingRunIds.add(runId);
            this.#refreshRequested = true;
            this.#startRefreshDrain(this.#generation.value);
        };

        bindAutomationRunActivityRealtimeSubscriptions({
            subscriptions: this.#websocketSubscriptions,
            notifyAutomationChanged: () => this.#notifyRealtimeListeners({ updateType: 'automation-changed' }),
            notifyRunChanged: (runId) => this.#notifyRealtimeListeners({ updateType: 'run-changed', runId }),
            scheduleRefreshForRun
        });
    }

    #bindAuthSubscriptions(): void {
        const auth = getAuthManager();
        this.#authSubscriptions.cleanup();
        try {
            this.#authSubscriptions.track(
                auth.onLogin(() => {
                    const generation = this.#generation.value;
                    void this.#primeInitialRunningSet(generation).catch((error) => {
                        log('error', 'Automation run activity initial sync failed', ensureError(error));
                    });
                })
            );
            this.#authSubscriptions.track(
                auth.onLogout(() => {
                    this.#generation.invalidate();
                    this.#pendingRunIds.clear();
                    this.#notFoundRunIds.clear();
                    this.#initialSyncInFlight = false;
                    this.#refreshInFlight = false;
                    this.#refreshRequested = false;
                    this.#state.reset();
                    this.#notifyListeners();
                })
            );
        } catch (subscriptionError) {
            this.#authSubscriptions.cleanup();
            throw subscriptionError;
        }
    }

    async #primeInitialRunningSet(generation: number): Promise<void> {
        if (!getAuthManager().isAuthenticated || !this.#isGenerationActive(generation)) {
            return;
        }
        if (this.#initialSyncInFlight) {
            return;
        }
        this.#initialSyncInFlight = true;
        try {
            this.#state.reset();
            this.#notFoundRunIds.clear();
            const payload = await this.#api.automations.runs.listActive();
            if (!Array.isArray(payload)) {
                throw new Error('Active automation runs response must be an array');
            }
            if (!getAuthManager().isAuthenticated || !this.#isGenerationActive(generation)) {
                return;
            }
            for (const record of payload) {
                const parsed = parseRunStatusFromRecord(record);
                this.#state.applyRunUpdate(parsed);
            }
            this.#state.markInitialized();
            this.#notifyListeners();
        } finally {
            if (this.#isGenerationActive(generation)) {
                this.#initialSyncInFlight = false;
                this.#startRefreshDrain(generation);
            }
        }
    }

    #startRefreshDrain(generation: number): void {
        if (!this.#initialized || this.#initialSyncInFlight || this.#refreshInFlight || !this.#refreshRequested || !this.#isGenerationActive(generation) || !getAuthManager().isAuthenticated) {
            return;
        }
        this.#refreshInFlight = true;
        void this.#drainRefreshQueue(generation).catch((error) => {
            log('error', 'Automation run activity refresh failed', ensureError(error));
        });
    }

    async #drainRefreshQueue(generation: number): Promise<void> {
        try {
            while (this.#refreshRequested && this.#isGenerationActive(generation) && getAuthManager().isAuthenticated) {
                this.#refreshRequested = false;
                const runIds = Array.from(this.#pendingRunIds);
                this.#pendingRunIds.clear();
                for (const runId of runIds) {
                    try {
                        const record = await this.#api.automations.runs.get(runId);
                        if (!this.#isGenerationActive(generation) || !getAuthManager().isAuthenticated) {
                            return;
                        }
                        this.#notFoundRunIds.delete(runId);
                        this.#state.applyRunUpdate(parseRunStatusFromRecord(record));
                    } catch (error) {
                        if (error instanceof APIError && error.status === 404) {
                            if (!this.#isGenerationActive(generation) || !getAuthManager().isAuthenticated) {
                                return;
                            }
                            this.#notFoundRunIds.add(runId);
                            this.#state.removeRun(runId);
                            continue;
                        }
                        throw error;
                    }
                }
                if (!this.#isGenerationActive(generation) || !getAuthManager().isAuthenticated) {
                    return;
                }
                this.#notifyListeners();
            }
        } finally {
            if (this.#isGenerationActive(generation)) {
                this.#refreshInFlight = false;
                this.#startRefreshDrain(generation);
            }
        }
    }

    #clearSubscriptions(): void {
        this.#websocketSubscriptions.cleanup();
        this.#authSubscriptions.cleanup();
    }

    #isGenerationActive(generation: number): boolean {
        return this.#generation.isActive(generation);
    }

    #notifyListeners(): void {
        const snapshot = this.getSnapshot();
        for (const listener of this.#listeners) {
            try {
                listener(snapshot);
            } catch (error) {
                log('warn', 'Automation run activity subscriber failed', ensureError(error));
            }
        }
    }

    #notifyRealtimeListeners(update: AutomationRealtimeUpdate): void {
        for (const listener of this.#realtimeListeners) {
            try {
                listener(update);
            } catch (error) {
                log('warn', 'Automation realtime subscriber failed', ensureError(error));
            }
        }
    }
}

export { AutomationRunActivityService };
