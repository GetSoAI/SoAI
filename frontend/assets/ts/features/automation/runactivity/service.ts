/* SoAI - Automation feature run activity service [frontend/assets/ts/features/automation/runactivity/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAuthManager } from '@core/auth/public.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import { isFunction } from '@core/typeGuards.ts';
import { AutomationRunningStateSynchronizer, type AutomationRunActivityApi } from '@features/automation/runactivity/AutomationRunningStateSynchronizer.ts';
import { bindAutomationRunActivityRealtimeSubscriptions } from '@features/automation/runactivity/realtimeSubscriptions.ts';
import type { AutomationRealtimeUpdate, AutomationRealtimeUpdateListener, AutomationRunActivityListener, AutomationRunActivityServiceContract, AutomationRunActivitySnapshot } from '@features/automation/runactivity/types.ts';

const log = createModuleLogger('AutomationRunActivityService', { defaultLevel: 'warn' });

class AutomationRunActivityService implements AutomationRunActivityServiceContract {
    readonly #synchronizer: AutomationRunningStateSynchronizer;
    readonly #listeners = new Set<AutomationRunActivityListener>();
    readonly #realtimeListeners = new Set<AutomationRealtimeUpdateListener>();
    readonly #authSubscriptions = new ResourceTracker();
    readonly #websocketSubscriptions = new ResourceTracker();
    readonly #generation = new SequenceToken();
    #initialized = false;
    #initializePromise: Promise<void> | null = null;

    constructor(api: AutomationRunActivityApi) {
        this.#synchronizer = new AutomationRunningStateSynchronizer(api, () => this.#notifyListeners());
    }

    getSnapshot(): AutomationRunActivitySnapshot {
        return this.#synchronizer.getSnapshot();
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
        if (!this.#synchronizer.isConnected()) listener({ updateType: 'connection-lost' });
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
        this.#synchronizer.dispose();
        this.#initialized = false;
        this.#initializePromise = null;
    }

    async #initialize(generation: number): Promise<void> {
        this.#bindRealtimeSubscriptions();
        this.#bindAuthSubscriptions();
        this.#synchronizer.setAuthenticated(getAuthManager().isAuthenticated);
        if (!getWebSocketClient().isConnected()) this.#synchronizer.noteConnectionLost();
        if (getAuthManager().isAuthenticated) {
            await this.#resyncRunningSet();
        }
        if (this.#generation.isActive(generation)) this.#initialized = true;
    }

    #bindRealtimeSubscriptions(): void {
        bindAutomationRunActivityRealtimeSubscriptions({
            subscriptions: this.#websocketSubscriptions,
            notifyAutomationChanged: () => this.#notifyRealtimeListeners({ updateType: 'automation-changed' }),
            notifyRunChanged: (runId) => this.#notifyRealtimeListeners({ updateType: 'run-changed', runId }),
            notifyConnectionLost: () => {
                this.#synchronizer.noteConnectionLost();
                this.#notifyRealtimeListeners({ updateType: 'connection-lost' });
            },
            notifyConnectionRestored: () => {
                if (this.#synchronizer.noteConnectionRestored()) terminateHandledPromise(this.#resyncRunningSet());
                this.#notifyRealtimeListeners({ updateType: 'connection-restored' });
            },
            scheduleRefreshForRun: (runId) => this.#synchronizer.noteRunChanged(runId)
        });
    }

    #bindAuthSubscriptions(): void {
        const auth = getAuthManager();
        this.#authSubscriptions.cleanup();
        try {
            this.#authSubscriptions.track(
                auth.onLogin(() => {
                    this.#synchronizer.setAuthenticated(true);
                    terminateHandledPromise(this.#resyncRunningSet());
                })
            );
            this.#authSubscriptions.track(
                auth.onLogout(() => {
                    this.#synchronizer.setAuthenticated(false);
                })
            );
        } catch (error) {
            this.#authSubscriptions.cleanup();
            throw ensureError(error);
        }
    }

    async #resyncRunningSet(): Promise<void> {
        try {
            await this.#synchronizer.synchronize();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isAbortError(runtimeError)) log('debug', 'Automation running set is awaiting recovery', runtimeError);
        }
    }

    #clearSubscriptions(): void {
        this.#websocketSubscriptions.cleanup();
        this.#authSubscriptions.cleanup();
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
