/* SoAI - Shared main status monitor stream bridge [frontend/assets/ts/core/mainstatusmonitor/streamBridge.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { getStatusStream, validateMainStatusStreamManager } from '@core/mainstatusmonitor/stream.ts';
import type { StreamManagerInterface, StreamSnapshot } from '@core/mainstatusmonitor/types.ts';
import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import { isAbortError } from '@core/errors/abort.ts';

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

    async getReadyStreamManager(signal?: AbortSignal): Promise<StreamManagerInterface> {
        const manager = this.#getStreamManager();
        await ensureStreamManagerReady(manager.resources, { allowDiscovery: true, signal });
        return manager;
    }

    resolveStreamManager(signal?: AbortSignal): StreamManagerInterface {
        const manager = this.#getStreamManager();
        const readyTask = ensureStreamManagerReady(manager.resources, { allowDiscovery: true, signal });
        void readyTask.catch((error) => {
            const runtimeError = ensureError(error);
            if (isAbortError(runtimeError) || isLifecycleCancellationError(runtimeError)) {
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
        const unsubscribe = this.#unsubscribeStream;
        this.#unsubscribeStream = null;
        if (typeof unsubscribe === 'function') {
            try {
                unsubscribe();
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('MainStatusMonitor', 'Failed to remove stream subscription', runtimeError);
            }
        }
    }

    reset(): void {
        this.disconnect();
        this.#streamManager = null;
    }

    async connect(inputArguments: { generation: number; isGenerationActive: (generation: number) => boolean; signal?: AbortSignal; onSnapshot: (snapshot: StreamSnapshot | null) => void }): Promise<boolean> {
        const generation = inputArguments.generation;
        const streamManager = this.resolveStreamManager(inputArguments.signal);
        if (!inputArguments.isGenerationActive(generation)) {
            return false;
        }

        this.disconnect();
        if (!inputArguments.isGenerationActive(generation)) {
            return false;
        }

        const statusStream = getStatusStream();
        const state = streamManager.resources.getResource(statusStream, { state: true });
        inputArguments.onSnapshot(state);
        if (!inputArguments.isGenerationActive(generation)) return false;

        const unsubscribe = streamManager.subscriptions.subscribeResourceState(statusStream, (snapshot: StreamSnapshot) => {
            if (!inputArguments.isGenerationActive(generation)) {
                return;
            }
            inputArguments.onSnapshot(snapshot);
        });
        if (!inputArguments.isGenerationActive(generation)) {
            unsubscribe?.();
            return false;
        }
        if (typeof unsubscribe !== 'function') throw new Error('Main status subscription must provide cleanup');
        this.#unsubscribeStream = unsubscribe;

        try {
            await streamManager.resources.ensureResourceStarted(statusStream, { signal: inputArguments.signal });
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isAbortError(runtimeError) || isLifecycleCancellationError(runtimeError)) {
                return inputArguments.isGenerationActive(generation);
            }
            errorHandler.warn('MainStatusMonitor', `Failed to start ${statusStream} stream`, runtimeError);
        }

        return inputArguments.isGenerationActive(generation);
    }
}

export { MainStatusStreamBridge };
