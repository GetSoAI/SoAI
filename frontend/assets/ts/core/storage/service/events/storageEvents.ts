/* SoAI - Frontend storage runtime event ownership [frontend/assets/ts/core/storage/service/events/storageEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { compareCrossTabRevision, type CrossTabRevision } from '@core/crosstab/revision.ts';
import { createMicrotaskScheduler } from '@core/primitives/microtaskScheduler.ts';
import { readPreferenceRequestIdentity } from '@core/storage/chatpreferences/preferenceRequestIdentity.ts';
import { serializeStorageGroup } from '@core/storage/persistence/storageGroupSerialization.ts';
import { normalizeStorageSyncSnapshot } from '@core/storage/service/syncSnapshot.ts';
import { isString } from '@core/typeGuards.ts';
import { mergeRemotePreferences } from '@core/storage/persistence/mergeremotepreferences/public.ts';
import { INTERNAL_REMOTE_KEYS } from '@core/storage/keys.ts';
import type { StorageRuntimeEvents, StorageRuntimeEventDependencies, StorageUiPreferenceChange } from '@core/storage/service/types.ts';
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

    const subscribeUiPreferenceChanges: StorageRuntimeEvents['subscribeUiPreferenceChanges'] = (listener) => {
        let active = true;
        let pending: StorageUiPreferenceChange | null = null;
        let committed: Readonly<CrossTabRevision> | null = null;
        let observedChecksum = adapters.serialize(serializeStorageGroup(state.cache, 'ui'));
        let unsubscribe: (() => void) | null = null;
        const notify = createMicrotaskScheduler(
            () => {
                const incoming = pending;
                pending = null;
                if (!incoming || incoming.authEpoch !== state.readAuthEpoch() || incoming.userId !== (readPreferenceRequestIdentity(state)?.userId ?? null)) return;
                if (compareCrossTabRevision(incoming.revision, state.sharedRevision) !== 0 || compareCrossTabRevision(incoming.revision, committed) <= 0) return;
                committed = incoming.revision;
                const checksum = adapters.serialize(serializeStorageGroup(state.cache, 'ui'));
                if (checksum === observedChecksum) return;
                observedChecksum = checksum;
                listener(incoming);
            },
            { label: 'StoragePreferences', isDisposed: () => !active }
        );
        const release = (): void => {
            if (!active) return;
            active = false;
            pending = null;
            const stop = unsubscribe;
            unsubscribe = null;
            state.resources.untrack(release);
            stop?.();
        };
        try {
            unsubscribe = dependencies.stateManager.subscribeTabState((event) => {
                if (!active || event.key !== state.stateKey) return;
                const snapshot = normalizeStorageSyncSnapshot(event.value ?? null);
                if (!snapshot || compareCrossTabRevision(snapshot.revision, pending?.revision ?? committed) <= 0) return;
                const userId = snapshot.session['userId'];
                pending = { authEpoch: state.readAuthEpoch(), userId: isString(userId) ? userId.trim() : null, source: snapshot.origin === state.windowIdentity ? 'local' : 'remote', revision: Object.freeze({ ...snapshot.revision }) };
                notify();
            });
            state.resources.track(release);
        } catch (error) {
            release();
            throw error;
        }
        return release;
    };

    return {
        subscribeUiPreferenceChanges,
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
