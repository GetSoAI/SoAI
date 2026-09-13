/* SoAI - Frontend main status monitor ownership [frontend/assets/ts/core/mainstatusmonitor/MainStatusMonitor.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { LifecycleModel } from '@core/LifecycleModel.ts';
import { requireMainStatusAuthManager } from '@core/mainstatusmonitor/auth.ts';
import { resolveMainStatusUpdate } from '@core/mainstatusmonitor/status.ts';
import { getStatusStream } from '@core/mainstatusmonitor/stream.ts';
import { MainStatusStreamBridge } from '@core/mainstatusmonitor/streamBridge.ts';
import { StatusSubscribers } from '@core/mainstatusmonitor/subscribers.ts';
import type { StatusCallback } from '@core/mainstatusmonitor/types.ts';
import { createModuleLogger } from '@core/moduleContext.ts';
import type { SystemStatusResource } from '@core/realtime/streammanager/resourceRegistry.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

const log = createModuleLogger('MainStatusMonitor', { defaultLevel: 'warn' });

class MainStatusMonitor extends LifecycleModel {
    #bindDataHubPromise: Promise<boolean> | null = null;
    #dataHubBound: boolean = false;
    #generation: number = 0;
    #activityAbort: AbortController = new AbortController();
    #subscribers: StatusSubscribers;
    #streamBridge: MainStatusStreamBridge;

    currentState: string;
    initialFetchInFlight: Promise<null | void> | null;

    constructor() {
        super({ name: 'mainStatusMonitor', type: 'service' });
        this.#subscribers = new StatusSubscribers({
            logWarn: (message: string, error: Error): void => {
                log('warn', message, error);
            }
        });
        this.#streamBridge = new MainStatusStreamBridge();
        this.currentState = 'unknown';
        this.initialFetchInFlight = null;
    }

    #advanceGeneration(): number {
        this.#generation += 1;
        this.#activityAbort.abort();
        this.#activityAbort = new AbortController();
        return this.#generation;
    }

    #isGenerationActive(generation: number): boolean {
        return generation === this.#generation && !this.#activityAbort.signal.aborted;
    }

    #markUnknown(): void {
        if (this.currentState === 'unknown') return;
        this.currentState = 'unknown';
        this.#subscribers.notify(this.currentState);
    }

    async initialize(): Promise<void> {
        if (this.isInitialized) return;
        if (this.isDestroyed) this.resetLifecycleState();
        await this.initializeLifecycle();
    }

    override async onInitialize(): Promise<void> {
        void this.ensureDeclaredResources().catch((error) => {
            errorHandler.warn('MainStatusMonitor', 'Required stream resources declaration failed', error);
        });
        void this.bindDataHub().catch((error) => {
            errorHandler.warn('MainStatusMonitor', 'Initial status monitor bind failed', error);
        });
    }

    override getRequiredResources(): string[] {
        return [getStatusStream()];
    }

    async fetchInitialState(): Promise<null | void> {
        if (this.initialFetchInFlight) {
            return this.initialFetchInFlight;
        }
        const generation = this.#generation;
        const auth = requireMainStatusAuthManager();
        if (!auth.isAuthenticated) {
            return null;
        }
        const fetchInitialState = async (): Promise<void> => {
            const manager = await this.#streamBridge.getReadyStreamManager();
            if (!this.#isGenerationActive(generation)) {
                return;
            }
            const statusStream = getStatusStream();
            const state = manager.resources.getResource(statusStream, { state: true });
            if (state && typeof state === 'object' && 'value' in state && state.value) {
                this.handleStatusUpdate(state.value, generation);
                return;
            }
            await manager.resources.ensureResourceStarted(statusStream, { throwOnError: false });
            if (!this.#isGenerationActive(generation)) {
                return;
            }
            const updatedState = manager.resources.getResource(statusStream, { state: true });
            if (updatedState && typeof updatedState === 'object' && 'value' in updatedState && updatedState.value) {
                this.handleStatusUpdate(updatedState.value, generation);
            }
        };
        this.initialFetchInFlight = fetchInitialState().finally(() => {
            if (generation === this.#generation) {
                this.initialFetchInFlight = null;
            }
        });
        return this.initialFetchInFlight;
    }

    async bindStreamManager(): Promise<void> {
        const generation = this.#generation;
        this.disconnect();
        const bound = await this.#streamBridge.connect({
            generation,
            isGenerationActive: (generationValue) => this.#isGenerationActive(generationValue),
            onValue: (value: SystemStatusResource): void => {
                this.handleStatusUpdate(value, generation);
            },
            onError: (): void => {
                this.#markUnknown();
            }
        });
        if (!this.#isGenerationActive(generation)) {
            return;
        }
        this.#dataHubBound = bound;
    }

    handleStatusUpdate(value: SystemStatusResource, generation: number = this.#generation): void {
        if (!this.#isGenerationActive(generation)) {
            return;
        }
        const nextState = resolveMainStatusUpdate(value, this.currentState);
        if (nextState === null) {
            return;
        }
        this.currentState = nextState;
        this.#subscribers.notify(nextState);
    }

    subscribe(callback: StatusCallback): () => void {
        return this.#subscribers.subscribe(callback, this.currentState);
    }

    getCurrentState(): string {
        return this.currentState;
    }

    isConnectionHealthy(): boolean {
        return this.#streamBridge.isConnectionHealthy();
    }

    disconnect(): void {
        this.#streamBridge.disconnect();
        this.#dataHubBound = false;
    }

    override async onDestroy(): Promise<void> {
        this.reset();
        this.#subscribers.clear();
    }

    reset(): void {
        this.#advanceGeneration();
        this.disconnect();
        this.initialFetchInFlight = null;
        this.#streamBridge.reset();
        this.#markUnknown();
        this.#bindDataHubPromise = null;
        this.#dataHubBound = false;
    }

    bindDataHub(): Promise<boolean> {
        if (this.isDestroyed) {
            throw new Error('Main status monitor is destroyed');
        }
        if (this.#dataHubBound) {
            return Promise.resolve(true);
        }
        if (this.#bindDataHubPromise) {
            return this.#bindDataHubPromise;
        }
        const generation = this.#generation;
        const bindTask = async (): Promise<boolean> => {
            const initialState = await this.fetchInitialState();
            if (initialState === null) {
                return false;
            }
            if (!this.#isGenerationActive(generation)) {
                return false;
            }
            await this.bindStreamManager();
            if (!this.#isGenerationActive(generation) || !this.#dataHubBound) {
                return false;
            }
            this.#dataHubBound = true;
            return true;
        };
        this.#bindDataHubPromise = bindTask().finally(() => {
            this.#bindDataHubPromise = null;
        });
        return this.#bindDataHubPromise;
    }
}

const createMainStatusMonitor = (): MainStatusMonitor => new MainStatusMonitor();

const getMainStatusMonitor = (): MainStatusMonitor => {
    const candidate = resolveKernelService('core.mainStatusMonitor');
    if (!(candidate instanceof MainStatusMonitor)) {
        throw new Error('core.mainStatusMonitor is not registered');
    }
    return candidate;
};
const resetMainStatusMonitor = (): void => {
    getMainStatusMonitor().reset();
};

export { MainStatusMonitor, createMainStatusMonitor, getMainStatusMonitor, resetMainStatusMonitor };
