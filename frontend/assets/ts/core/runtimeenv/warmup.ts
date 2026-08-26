/* SoAI - Shared runtime environment warmup [frontend/assets/ts/core/runtimeenv/warmup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { isObject, isThenable } from '@core/typeGuards.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import { ensureStreamManager } from '@core/runtimeenv/guards.ts';
import { SYSTEM_LOGS_CORE_STREAM } from '@core/runtimeenv/serviceSupport.ts';
import type { DetachedSubscription } from '@core/runtimeenv/internalContracts.ts';

interface DetachedWarmupState {
    detachedWarmupTask: Promise<void> | null;
    detachedSubscription: DetachedSubscription | null;
}

interface LogWarmupState {
    logSnapshotTask: Promise<void> | null;
}

const isDetachedSubscription = <T>(value: T): value is T & DetachedSubscription => isObject(value) && 'ready' in value && isThenable(value.ready);

const warmDetachedBundle = async (inputArguments: { state: DetachedWarmupState; isPrimaryWindow: boolean; logDetachedWarning: (message: string, details?: TelemetryValue) => void }): Promise<void> => {
    const { state, isPrimaryWindow } = inputArguments;
    if (!isPrimaryWindow) {
        return;
    }
    if (state.detachedWarmupTask) {
        return state.detachedWarmupTask;
    }
    state.detachedWarmupTask = (async () => {
        const manager = ensureStreamManager();
        await ensureStreamManagerReady(manager.resources, { allowDiscovery: true, autoResources: true });
        if (!state.detachedSubscription) {
            const subscription = manager.subscriptions.subscribeBundle('detached', {}, { signal: null });
            if (!isDetachedSubscription(subscription)) {
                throw new Error('Detached subscription initialization failed');
            }
            state.detachedSubscription = subscription;
        }
        const ready = state.detachedSubscription.ready;
        await ready;
    })().finally(() => {
        state.detachedWarmupTask = null;
    });
    try {
        await state.detachedWarmupTask;
    } catch (error) {
        const detail = error instanceof Error || typeof error === 'string' ? error : String(error);
        inputArguments.logDetachedWarning('Detached warmup failed', detail);
        throw error;
    }
};

const warmLogBundle = async (inputArguments: { state: LogWarmupState; isPrimaryWindow: boolean }): Promise<void> => {
    const { state, isPrimaryWindow } = inputArguments;
    if (!isPrimaryWindow) {
        return;
    }
    if (state.logSnapshotTask) {
        return state.logSnapshotTask;
    }
    state.logSnapshotTask = (async () => {
        const manager = ensureStreamManager();
        await ensureStreamManagerReady(manager.resources, { allowDiscovery: true });
        await manager.resources.ensureResourceStarted(SYSTEM_LOGS_CORE_STREAM);
    })().finally(() => {
        state.logSnapshotTask = null;
    });
    return state.logSnapshotTask;
};

export { warmDetachedBundle, warmLogBundle };
