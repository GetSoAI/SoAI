/* SoAI - Shared connection state effects [frontend/assets/ts/core/connectionstate/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import { requireStateManager } from '@core/state/runtime.ts';
import { applyStorageSnapshot } from '@core/connectionstate/actions.ts';
import type { StateManager, UpdateOptions } from '@core/connectionstate/contracts.ts';
import type { ConnectionStateState } from '@core/connectionstate/state.ts';
import { isStateManager } from '@core/connectionstate/internalContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface SnapshotBridgeCallbacks {
    notifyListeners: (value: string | null) => void;
    resolveWaiters: (value: string) => void;
    updateBaseUrl: (value: string | null, options: UpdateOptions) => string | null;
    normalizeBaseUrl: (value: string) => string | null;
    onWarn: (message: string, error: Error) => void;
}

const resolveStateManager = async (): Promise<StateManager> => {
    const manager = requireStateManager();
    if (!isStateManager(manager)) {
        throw new Error('State manager must expose tab state accessors for connection state');
    }
    return manager;
};

const connectStorageSnapshotBridge = async (state: ConnectionStateState, callbacks: SnapshotBridgeCallbacks): Promise<void> => {
    if (state.snapshotBridgePromise) {
        await state.snapshotBridgePromise;
        return;
    }

    if (state.stateManager && state.stateSubscription) {
        return;
    }

    state.snapshotBridgePromise = (async () => {
        const manager = await resolveStateManager();
        state.stateManager = manager;

        const snapshot = manager.getTabState(state.snapshotKey);
        if (!isNullOrUndefined(snapshot)) {
            try {
                applyStorageSnapshot(state, snapshot, {
                    normalizeBaseUrl: callbacks.normalizeBaseUrl,
                    updateBaseUrl: callbacks.updateBaseUrl
                });
            } catch (error) {
                const runtimeError = ensureError(error);
                callbacks.onWarn('ConnectionState failed to apply initial storage snapshot', runtimeError);
            }
        }

        state.stateSubscription = manager.subscribeTabState((event) => {
            if (!event || event.key !== state.snapshotKey) {
                return;
            }
            if (!isObject(event.value)) {
                callbacks.onWarn('ConnectionState received invalid storage snapshot payload', new TypeError('ConnectionState received invalid storage snapshot payload'));
                return;
            }

            try {
                applyStorageSnapshot(state, event.value, {
                    normalizeBaseUrl: callbacks.normalizeBaseUrl,
                    updateBaseUrl: callbacks.updateBaseUrl
                });
            } catch (error) {
                const runtimeError = ensureError(error);
                callbacks.onWarn('ConnectionState failed to apply storage snapshot', runtimeError);
            }
        });
    })();

    try {
        await state.snapshotBridgePromise;
    } finally {
        state.snapshotBridgePromise = null;
    }
};

export { connectStorageSnapshotBridge };
