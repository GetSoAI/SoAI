/* SoAI - Shared storage persistence [frontend/assets/ts/core/storage/service/events/persistence.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { handleApiResult } from '@core/api/apiResultHandler.ts';
import { isNetworkError, type APIErrorMetadataValue } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { serializeChatCache } from '@core/storage/persistence/chatPreferenceSerialization.ts';
import { serializeStorageGroup } from '@core/storage/persistence/storageGroupSerialization.ts';
import type { StorageAdapters } from '@core/storage/service/adapters.ts';
import type { StorageRuntimeDependencies, StorageRuntimeState } from '@core/storage/service/types.ts';
import type { SyncGroup } from '@core/storage/types.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { ChatPreferencePersistenceController } from '@core/storage/chatpreferences/ChatPreferencePersistenceController.ts';
import type { ChatPreferenceGenerations } from '@core/storage/chatpreferences/chatPreferenceReconciliation.ts';
import type { CrossTabPublishOutcome } from '@core/crosstab/channel.ts';
import { enqueuePreferenceOperation } from '@core/storage/chatpreferences/preferenceOperationQueue.ts';
import { preferenceRequestIdentityIsCurrent, readPreferenceRequestIdentity } from '@core/storage/chatpreferences/preferenceRequestIdentity.ts';

interface StorageBroadcastBridge {
    requestBroadcast: () => void;
}
interface StoragePersistenceDependencies {
    state: StorageRuntimeState;
    dependencies: StorageRuntimeDependencies;
    adapters: StorageAdapters;
    broadcastBridge: StorageBroadcastBridge;
}
interface StoragePersistenceHandlers {
    persistedGroupKeys: readonly string[];
    syncLocal: (group: string) => void;
    queuePersist: (group: string) => Promise<JsonValue | null>;
    flushPending: () => Promise<void>;
    ensureMainState: () => void;
    updatePersisted: (group: string) => void;
    refreshChatPreferences: (options?: { authTransitionOwned?: boolean }) => Promise<JsonObject>;
    persistChatPreferencePatch: (patch: JsonObject) => Promise<JsonObject>;
    prepareChatPreferencePatch: (patch: JsonObject) => () => Promise<JsonObject>;
    prepareExternalChatPreferenceProjection: () => (patch: JsonObject) => Promise<void>;
    prepareChatPreferenceInvalidation: () => () => CrossTabPublishOutcome | null;
    pendingConversationDefaults: () => JsonObject;
}
const createGroupPayloadFactories = (state: StorageRuntimeState, adapters: StorageAdapters): Record<string, () => JsonObject> => {
    const payloadForGroup = (group: SyncGroup | 'misc'): JsonObject => {
        if (group === 'misc') return { misc: adapters.clone(state.cache.misc) };
        return { [group]: serializeStorageGroup(state.cache, group) };
    };
    const factories: Record<string, () => JsonObject> = {};
    const persistGroups: readonly (SyncGroup | 'misc')[] = ['ui', 'chat', 'logs', 'terminal', 'search', 'hardware', 'filters', 'wizard', 'settings', 'misc'];
    for (const group of persistGroups) {
        factories[group] = () => payloadForGroup(group);
    }
    return factories;
};
const createStoragePersistenceHandlers = ({ state, dependencies, adapters, broadcastBridge }: StoragePersistenceDependencies): StoragePersistenceHandlers => {
    const groupPayloadFactories = createGroupPayloadFactories(state, adapters);
    const persistedGroupKeys = Object.keys(groupPayloadFactories);
    const updatePersisted = (group: string): void => {
        const factory = groupPayloadFactories[group];
        if (!factory) {
            delete state.persistedChecksums[group];
            return;
        }
        const payload = factory();
        const groupValue = payload[group];
        if (groupValue === undefined) {
            delete state.persistedChecksums[group];
            return;
        }
        state.persistedChecksums[group] = adapters.serialize(groupValue);
    };
    const syncLocal = (group: string): void => {
        if (!state.localStorageAvailable) {
            return;
        }
        const keys = state.localKeys;
        if (group === 'ui') {
            adapters.writeStorage('localStorage', keys.theme, state.cache.ui.theme);
            adapters.writeStorage('localStorage', keys.accentColor, state.cache.ui.accentColor);
            adapters.writeStorage('localStorage', keys.surfaceColor, state.cache.ui.surfaceColor);
            adapters.writeStorage('localStorage', keys.language, state.cache.ui.language);
            adapters.writeStorage('localStorage', keys.animationSpeed, state.cache.ui.animationSpeed);
            adapters.writeStorage('localStorage', keys.interfaceScale, state.cache.ui.interfaceScale);
            return;
        }
        if (group === 'chat') {
            adapters.writeStorage('localStorage', keys.chat, serializeChatCache(state.cache.chat));
            return;
        }
        if (group === 'logs') {
            adapters.writeStorage('localStorage', keys.logs, serializeStorageGroup(state.cache, 'logs'));
            return;
        }
        void keys;
    };
    const ensureMainState = (): void => {
        const ui = state.cache.ui;
        if ((Number(ui.mainStatePreferenceVersion) || 0) < 1) {
            ui.showMainStatusIndicator = true;
            ui.mainStatePreferenceVersion = 1;
            terminateHandledPromise(queuePersist('ui'));
        }
    };
    const chatPreferences = new ChatPreferencePersistenceController({ state, adapters, apiClient: dependencies.apiClient, stateManager: dependencies.stateManager, syncLocal: () => syncLocal('chat'), updatePersisted: () => updatePersisted('chat') });
    const queuePersist = (group: string): Promise<JsonValue | null> => {
        if (!group) {
            return Promise.resolve(null);
        }
        syncLocal(group);
        broadcastBridge.requestBroadcast();
        if (group === 'chat') return chatPreferences.queueLocalDrain();
        const factory = groupPayloadFactories[group];
        const localOnly = !factory;
        if (state.maintenanceHold && !localOnly) {
            state.pendingGroups.add(group);
            return Promise.resolve(null);
        }
        if (!state.isAuthenticated && !localOnly) {
            state.pendingGroups.add(group);
            return Promise.resolve(null);
        }
        if (localOnly) {
            state.pendingGroups.delete(group);
            return Promise.resolve(null);
        }
        const identity = readPreferenceRequestIdentity(state);
        if (!identity) {
            state.pendingGroups.add(group);
            return Promise.resolve(null);
        }
        const payload = factory();
        const groupValue = payload[group];
        if (groupValue === undefined) {
            state.pendingGroups.delete(group);
            return Promise.resolve(null);
        }
        const checksum = adapters.serialize(groupValue);
        const latestScheduledChecksum = state.queuedChecksums[group] ?? state.inflightChecksums[group] ?? state.persistedChecksums[group];
        if (latestScheduledChecksum === checksum) {
            state.pendingGroups.delete(group);
            return Promise.resolve(null);
        }
        state.pendingGroups.delete(group);
        state.queuedChecksums[group] = checksum;
        const task = enqueuePreferenceOperation(state, async () => {
            if (!preferenceRequestIdentityIsCurrent(state, identity)) {
                if (state.queuedChecksums[group] === checksum) delete state.queuedChecksums[group];
                return null;
            }
            if (state.maintenanceHold) {
                state.pendingGroups.add(group);
                if (state.queuedChecksums[group] === checksum) delete state.queuedChecksums[group];
                return null;
            }
            state.inflightChecksums[group] = checksum;
            const updateFunction = dependencies.apiClient?.webui?.preferences?.update;
            if (!updateFunction) {
                state.pendingGroups.add(group);
                if (state.inflightChecksums[group] === checksum) {
                    delete state.inflightChecksums[group];
                }
                if (state.queuedChecksums[group] === checksum) {
                    delete state.queuedChecksums[group];
                }
                return null;
            }
            try {
                const captured: ChatPreferenceGenerations = chatPreferences.captureRequest();
                const result = await handleApiResult(updateFunction(payload), {
                    boundaryName: 'StorageManager',
                    notifyOnError: false,
                    rethrow: (error: APIErrorMetadataValue) => {
                        if (isNetworkError(error)) {
                            if (preferenceRequestIdentityIsCurrent(state, identity)) state.pendingGroups.add(group);
                            return false;
                        }
                        return true;
                    }
                });
                if (preferenceRequestIdentityIsCurrent(state, identity)) {
                    if (isJsonObject(result)) {
                        chatPreferences.applyExternalResponse(result, captured);
                        state.persistedChecksums[group] = checksum;
                    } else {
                        state.pendingGroups.add(group);
                    }
                }
            } catch (error) {
                if (preferenceRequestIdentityIsCurrent(state, identity)) state.pendingGroups.add(group);
                const runtimeError = ensureError(error);
                errorHandler.warn('StorageManager', `Persist failed for group ${group}`, runtimeError);
            } finally {
                if (state.inflightChecksums[group] === checksum) {
                    delete state.inflightChecksums[group];
                }
                if (state.queuedChecksums[group] === checksum) {
                    delete state.queuedChecksums[group];
                }
            }
            return null;
        });
        return task;
    };
    const flushPending = async (): Promise<void> => {
        if (!state.isAuthenticated) {
            return;
        }
        const identity = readPreferenceRequestIdentity(state);
        if (!identity) return;
        if (state.pendingGroups.has('chat')) await chatPreferences.queueLocalDrain();
        if (!preferenceRequestIdentityIsCurrent(state, identity)) return;
        await enqueuePreferenceOperation(state, async (): Promise<void> => {
            if (!preferenceRequestIdentityIsCurrent(state, identity) || state.maintenanceHold) return;
            const payload: JsonObject = {};
            const checksums = new Map<string, string>();
            const queued: string[] = [];
            for (const group of state.pendingGroups) {
                if (group === 'chat') continue;
                state.pendingGroups.delete(group);
                const factory = groupPayloadFactories[group];
                if (!factory) continue;
                const groupPayload = factory();
                const groupValue = groupPayload[group];
                if (groupValue === undefined) continue;
                const checksum = adapters.serialize(groupValue);
                if ([state.persistedChecksums[group], state.inflightChecksums[group], state.queuedChecksums[group]].includes(checksum)) continue;
                Object.assign(payload, groupPayload);
                checksums.set(group, checksum);
                queued.push(group);
            }
            if (!queued.length) return;
            for (const group of queued) {
                const checksum = checksums.get(group);
                if (!checksum) throw new Error(`Missing checksum for group ${group}`);
                state.queuedChecksums[group] = checksum;
                state.inflightChecksums[group] = checksum;
            }
            const updateFunction = dependencies.apiClient?.webui?.preferences?.update;
            if (!updateFunction) {
                for (const group of queued) {
                    delete state.inflightChecksums[group];
                    delete state.queuedChecksums[group];
                    state.pendingGroups.add(group);
                }
                throw new Error('Authenticated preference persistence is unavailable.');
            }
            try {
                const captured = chatPreferences.captureRequest();
                const result = await handleApiResult(updateFunction(payload), { boundaryName: 'StorageManager', notifyOnError: false, rethrow: true });
                if (preferenceRequestIdentityIsCurrent(state, identity)) {
                    if (!isJsonObject(result)) throw new Error('Authoritative preference response must be an object.');
                    chatPreferences.applyExternalResponse(result, captured);
                    for (const group of queued) {
                        const checksum = checksums.get(group);
                        if (!checksum) throw new Error(`Missing checksum for group ${group}`);
                        state.persistedChecksums[group] = checksum;
                    }
                }
                for (const group of queued) {
                    delete state.inflightChecksums[group];
                    delete state.queuedChecksums[group];
                }
            } catch (error) {
                const runtimeError = ensureError(error);
                for (const group of queued) {
                    delete state.inflightChecksums[group];
                    delete state.queuedChecksums[group];
                    if (preferenceRequestIdentityIsCurrent(state, identity)) state.pendingGroups.add(group);
                }
                throw runtimeError;
            }
        });
    };
    return {
        persistedGroupKeys,
        syncLocal,
        queuePersist,
        flushPending,
        ensureMainState,
        updatePersisted,
        refreshChatPreferences: (options) => chatPreferences.refresh(options),
        persistChatPreferencePatch: (patch) => chatPreferences.persistPatch(patch),
        prepareChatPreferencePatch: (patch) => chatPreferences.preparePatch(patch),
        prepareExternalChatPreferenceProjection: () => chatPreferences.prepareExternalProjection(),
        prepareChatPreferenceInvalidation: () => chatPreferences.prepareInvalidationPublication(),
        pendingConversationDefaults: () => chatPreferences.pendingConversationDefaults()
    };
};
export { createStoragePersistenceHandlers };
