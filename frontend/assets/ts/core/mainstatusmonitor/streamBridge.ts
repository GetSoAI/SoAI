/* SoAI - Shared main status monitor stream bridge [frontend/assets/ts/core/mainstatusmonitor/streamBridge.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { getStatusStream, validateMainStatusStreamManager } from '@core/mainstatusmonitor/stream.ts';
import type { StreamManagerInterface, StreamSnapshot } from '@core/mainstatusmonitor/types.ts';
import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import type { SystemStatusResource } from '@core/realtime/streammanager/resourceRegistry.ts';

class MainStatusStreamBridge {
    #unsubscribeStream: (() => void) | null = null;
    #streamManager: StreamManagerInterface | null = null;

    #getStreamManager(): StreamManagerInterface {
        if (this.#streamManager) {
            return validateMainStatusStreamManager(this.#streamManager);
        }
        const manager = validateMainStatusStreamManager(getStreamRuntime());
        this.#streamManager = manager;
        return manager;
    }

    async getReadyStreamManager(): Promise<StreamManagerInterface> {
        const manager = this.#getStreamManager();
        await ensureStreamManagerReady(manager.resources, { allowDiscovery: true });
        return manager;
    }

    resolveStreamManager(): StreamManagerInterface {
        const manager = this.#getStreamManager();
        const readyTask = ensureStreamManagerReady(manager.resources, { allowDiscovery: true });
        void readyTask.catch((error) => {
            const runtimeError = ensureError(error);
            if (isLifecycleCancellationError(runtimeError)) {
                return;
            }
            errorHandler.warn('MainStatusMonitor', 'Stream manager readiness refresh failed', runtimeError);
        });
        return manager;
    }

    isConnectionHealthy(): boolean {
        return typeof this.#unsubscribeStream === 'function';
    }

    disconnect(): void {
        if (typeof this.#unsubscribeStream === 'function') {
            try {
                this.#unsubscribeStream();
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('MainStatusMonitor', 'Failed to remove stream subscription', runtimeError);
            }
        }
        this.#unsubscribeStream = null;
    }

    reset(): void {
        this.disconnect();
        this.#streamManager = null;
    }

    async connect(inputArguments: { generation: number; isGenerationActive: (generation: number) => boolean; onValue: (value: SystemStatusResource) => void; onError: () => void }): Promise<boolean> {
        const generation = inputArguments.generation;
        const streamManager = this.resolveStreamManager();
        if (!inputArguments.isGenerationActive(generation)) {
            return false;
        }

        this.disconnect();
        if (!inputArguments.isGenerationActive(generation)) {
            return false;
        }

        const statusStream = getStatusStream();
        const state = streamManager.resources.getResource(statusStream, { state: true });
        if (state?.status === 'ready' && state.value) {
            inputArguments.onValue(state.value);
        }

        const unsubscribe = streamManager.subscriptions.subscribeResourceState(statusStream, (snapshot: StreamSnapshot) => {
            if (!inputArguments.isGenerationActive(generation)) {
                return;
            }
            if (snapshot.status === 'ready' && snapshot.value) {
                inputArguments.onValue(snapshot.value);
            } else if (snapshot.status === 'error') {
                inputArguments.onError();
            }
        });
        if (typeof unsubscribe === 'function') {
            this.#unsubscribeStream = unsubscribe;
        }

        try {
            await streamManager.resources.ensureResourceStarted(statusStream);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isLifecycleCancellationError(runtimeError)) {
                return inputArguments.isGenerationActive(generation);
            }
            errorHandler.warn('MainStatusMonitor', `Failed to start ${statusStream} stream`, runtimeError);
        }

        return inputArguments.isGenerationActive(generation);
    }
}

export { MainStatusStreamBridge };
