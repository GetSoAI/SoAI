/* SoAI - Shared frontend storage service runtime [frontend/assets/ts/core/storage/service/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { STORAGE_LOCAL_KEYS } from '@core/storage/keys.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { createStorageDefaults } from '@core/storage/defaults.ts';
import type { StorageSyncSnapshot } from '@core/storage/service/syncSnapshot.ts';
import { createStorageAdapters } from '@core/storage/service/adapters.ts';
import { createStorageEffects } from '@core/storage/service/effects.ts';
import { createStorageEvents } from '@core/storage/service/events/public.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { StorageRuntime, StorageRuntimeDependencies, StorageRuntimeState } from '@core/storage/service/types.ts';

const createStorageState = (): StorageRuntimeState => {
    const currentWindowIdentity = windowIdentity.current();
    return {
        defaults: createStorageDefaults(),
        cache: createStorageDefaults(),
        pendingGroups: new Set(),
        writeQueue: Promise.resolve(null),
        windowIdentity: currentWindowIdentity,
        windowIdentityReady: Promise.resolve(currentWindowIdentity),
        isAuthenticated: false,
        session: {},
        stateKey: 'core.storage.snapshot',
        sharedRevision: null,
        persistedChecksums: {},
        inflightChecksums: {},
        queuedChecksums: {},
        resources: new ResourceTracker(),
        localKeys: STORAGE_LOCAL_KEYS,
        localStorageAvailable: false,
        sessionStorageAvailable: false,
        maintenanceHold: false,
        sharedBroadcastHandle: null
    };
};

const createStorageRuntime = ({ apiClient, stateManager }: StorageRuntimeDependencies): StorageRuntime => {
    const state = createStorageState();
    const adapters = createStorageAdapters(state);
    const effects = createStorageEffects();
    const createDefaults = (): ReturnType<typeof createStorageDefaults> => adapters.clone(state.defaults);
    const events = createStorageEvents({
        state,
        dependencies: {
            apiClient,
            stateManager
        },
        createDefaults,
        adapters,
        effects
    });

    return {
        state,
        ready: events.ready,
        clone: adapters.clone,
        createDefaults,
        writeStorage: adapters.writeStorage,
        queuePersist: events.queuePersist,
        flushPending: events.flushPending,
        mergeRemote: events.mergeRemote,
        refreshChatPreferences: events.refreshChatPreferences,
        persistChatPreferencePatch: events.persistChatPreferencePatch,
        prepareChatPreferencePatch: events.prepareChatPreferencePatch,
        prepareExternalChatPreferenceProjection: events.prepareExternalChatPreferenceProjection,
        prepareChatPreferenceInvalidation: events.prepareChatPreferenceInvalidation,
        pendingConversationDefaults: events.pendingConversationDefaults,
        syncLocal: events.syncLocal,
        scheduleBroadcast: events.scheduleBroadcast,
        applyTheme: events.applyTheme,
        bodyClass: effects.bodyClass,
        setGlassDisabled: effects.setGlassDisabled,
        setAttr: effects.setAttr,
        reapplyHeaderStats: effects.reapplyHeaderStats,
        normalizeLimit: adapters.normalizeLimit,
        normalizeZoom: adapters.normalizeZoom,
        ensureMainState: events.ensureMainState
    };
};

export { createStorageRuntime };
export type { StorageSyncSnapshot };
