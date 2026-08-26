/* SoAI - Shared storage sync contracts [frontend/assets/ts/core/storage/service/events/sync/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StorageAdapters, StorageRuntimeDependencies, StorageRuntimeState, StorageUiEffects, ThemeApplyOptions } from '@core/storage/service/types.ts';
import type { StorageCache } from '@core/storage/types.ts';
import type { StorageSyncSnapshot } from '@core/storage/service/syncSnapshot.ts';

interface StorageSyncState {
    syncLocal: (group: string) => void;
    ensureMainState: () => void;
    flushPending: () => Promise<void>;
}

interface StorageSyncHandlers {
    scheduleBroadcast: () => void;
    applyTheme: (preference: string, options?: ThemeApplyOptions) => string;
    ready: Promise<void>;
}

interface StorageSyncDependencies extends StorageSyncState {
    state: StorageRuntimeState;
    dependencies: StorageRuntimeDependencies;
    createDefaults: () => StorageCache;
    adapters: StorageAdapters;
    effects: StorageUiEffects;
}

interface StorageSyncAdapterContext {
    state: StorageRuntimeState;
    dependencies: StorageRuntimeDependencies;
    createDefaults: () => StorageCache;
    adapters: StorageAdapters;
    effects: StorageUiEffects;
    syncLocal: (group: string) => void;
    ensureMainState: () => void;
}

interface StorageSyncApplyLocalContext {
    state: StorageRuntimeState;
    adapters: StorageAdapters;
    effects: StorageUiEffects;
    syncLocal: (group: string) => void;
    ensureMainState: () => void;
    applyTheme: (preference: string, options?: ThemeApplyOptions) => string;
}

interface StorageSyncBootstrapContext {
    state: StorageRuntimeState;
    adapters: StorageAdapters;
    effects: StorageUiEffects;
    flushPending: () => Promise<void>;
    applyTheme: (preference: string, options?: ThemeApplyOptions) => string;
    ensureMainState: () => void;
    syncLocal: (group: string) => void;
    scheduleBroadcast: () => void;
    connectShared: () => Promise<void>;
    broadcast: () => Promise<void>;
    applyLocal: () => void;
}

interface StorageSyncAdapterHandlers {
    scheduleBroadcast: () => void;
    broadcast: () => Promise<void>;
    connectShared: (applyTheme: (preference: string, options?: ThemeApplyOptions) => string) => Promise<void>;
}

interface StorageSyncApplySnapshotBridge {
    applyTheme: (preference: string, options?: ThemeApplyOptions) => string;
    ensureMainState: () => void;
    syncLocal: (group: string) => void;
    scheduleBroadcast: () => void;
}

export type { StorageSyncSnapshot, StorageSyncAdapterContext, StorageSyncAdapterHandlers, StorageSyncApplyLocalContext, StorageSyncApplySnapshotBridge, StorageSyncBootstrapContext, StorageSyncDependencies, StorageSyncHandlers, StorageSyncState };
