/* SoAI - Shared connection state storage [frontend/assets/ts/core/connectionstate/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ErrorHandler } from '@core/errorHandler.ts';
import type { BaseUrlListener, StorageService, StateManager, Waiter } from '@core/connectionstate/contracts.ts';

const DEFAULT_SNAPSHOT_KEY = 'core.storage.snapshot';

interface ConnectionStateState {
    errorHandler: ErrorHandler | undefined;
    listeners: Set<BaseUrlListener>;
    waiters: Set<Waiter>;
    storage: StorageService;
    storageKey: string;
    snapshotStorageKey: string;
    baseUrl: string | null;
    instanceId: string | null;
    persistedBaseUrl: string | null;
    allowConfiguredFallback: boolean;
    runtimeConfiguredBaseUrl: string | null;
    stateManager: StateManager | null;
    stateSubscription: (() => void) | null;
    snapshotBridgePromise: Promise<void> | null;
    initializePromise: Promise<void> | null;
    snapshotKey: string;
}

interface CreateConnectionStateOptions {
    errorHandler: ErrorHandler | undefined;
    storage: StorageService;
    storageKey: string;
    runtimeConfiguredBaseUrl: string | null;
}

const createConnectionStateState = ({ errorHandler, storage, storageKey, runtimeConfiguredBaseUrl }: CreateConnectionStateOptions): ConnectionStateState => {
    const trimmedStorageKey = storageKey.trim();

    return {
        errorHandler,
        listeners: new Set<BaseUrlListener>(),
        waiters: new Set<Waiter>(),
        storage,
        storageKey,
        snapshotStorageKey: trimmedStorageKey.startsWith('soai_') ? trimmedStorageKey : `soai_${trimmedStorageKey}`,
        baseUrl: runtimeConfiguredBaseUrl,
        instanceId: null,
        persistedBaseUrl: null,
        allowConfiguredFallback: true,
        runtimeConfiguredBaseUrl,
        stateManager: null,
        stateSubscription: null,
        snapshotBridgePromise: null,
        initializePromise: null,
        snapshotKey: DEFAULT_SNAPSHOT_KEY
    };
};

export { createConnectionStateState };
export type { ConnectionStateState };
