/* SoAI - Frontend storage runtime event ownership [frontend/assets/ts/core/storage/service/events/storageEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { mergeRemotePreferences } from '@core/storage/persistence/mergeremotepreferences/public.ts';
import { INTERNAL_REMOTE_KEYS } from '@core/storage/keys.ts';
import type { StorageRuntimeEvents, StorageRuntimeEventDependencies } from '@core/storage/service/types.ts';
import { createStoragePersistenceHandlers } from '@core/storage/service/events/persistence.ts';
import { createStorageSyncHandlers } from '@core/storage/service/events/sync/service.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const createStorageEvents = ({ state, dependencies, createDefaults, adapters, effects }: StorageRuntimeEventDependencies): StorageRuntimeEvents => {
    let requestBroadcast: () => void = () => {};

    const persistenceHandlers = createStoragePersistenceHandlers({
        state,
        dependencies,
        adapters,
        broadcastBridge: {
            requestBroadcast: () => {
                requestBroadcast();
            }
        }
    });

    const syncHandlers = createStorageSyncHandlers({
        state,
        dependencies,
        createDefaults,
        adapters,
        effects,
        syncLocal: persistenceHandlers.syncLocal,
        ensureMainState: persistenceHandlers.ensureMainState,
        flushPending: persistenceHandlers.flushPending
    });
    requestBroadcast = syncHandlers.scheduleBroadcast;

    const mergeRemote = (remote: JsonObject | null | undefined): void => {
        mergeRemotePreferences(
            {
                cache: state.cache,
                defaults: state.defaults,
                localStorageGroups: Object.freeze(['ui', 'chat', 'logs', 'misc']),
                internalRemoteKeys: INTERNAL_REMOTE_KEYS,
                persistedGroupKeys: persistenceHandlers.persistedGroupKeys,
                createDefaults,
                clone: adapters.clone,
                normalizeZoom: adapters.normalizeZoom,
                normalizeLimit: adapters.normalizeLimit,
                updatePersisted: persistenceHandlers.updatePersisted,
                syncLocal: persistenceHandlers.syncLocal,
                applyTheme: syncHandlers.applyTheme,
                bodyClass: effects.bodyClass,
                setGlassDisabled: effects.setGlassDisabled,
                setAttr: effects.setAttr,
                ensureMainState: persistenceHandlers.ensureMainState
            },
            remote
        );
    };

    return {
        syncLocal: persistenceHandlers.syncLocal,
        queuePersist: persistenceHandlers.queuePersist,
        flushPending: persistenceHandlers.flushPending,
        mergeRemote,
        refreshChatPreferences: persistenceHandlers.refreshChatPreferences,
        persistChatPreferencePatch: persistenceHandlers.persistChatPreferencePatch,
        prepareChatPreferencePatch: persistenceHandlers.prepareChatPreferencePatch,
        prepareExternalChatPreferenceProjection: persistenceHandlers.prepareExternalChatPreferenceProjection,
        prepareChatPreferenceInvalidation: persistenceHandlers.prepareChatPreferenceInvalidation,
        pendingConversationDefaults: persistenceHandlers.pendingConversationDefaults,
        scheduleBroadcast: syncHandlers.scheduleBroadcast,
        applyTheme: syncHandlers.applyTheme,
        ensureMainState: persistenceHandlers.ensureMainState,
        ready: syncHandlers.ready
    };
};

export { createStorageEvents };
export type { StorageRuntimeEvents };
