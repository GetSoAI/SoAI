/* SoAI - Shared frontend storage service events sync adapters [frontend/assets/ts/core/storage/service/events/sync/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent } from '@core/environment/public.ts';
import { EVENT_REQUEST } from '@core/languageservice/constants.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { toJsonCompatibleObject, toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { arraysEqual } from '@core/primitives/equality.ts';
import { clockPreferenceStatesEqual, dispatchClockPreferenceChanged, readClockPreferenceState } from '@core/storage/clockPreferences.ts';
import { syncLocalizationPreferencesFromUi } from '@core/storage/localizationPreferences.ts';
import { CHANGED_EVENTS } from '@core/storage/service/constants.ts';
import { applyPresentationPreferenceDomEffects } from '@core/storage/service/presentationpreferences/domEffects.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import { compareCrossTabRevision, createNextCrossTabRevision, serializeCrossTabRevision } from '@core/crosstab/revision.ts';
import { CROSS_TAB_SYNC_GROUPS, LOCAL_STORAGE_GROUPS } from '@core/storage/namespaces.ts';
import { normalizeSessionData } from '@core/storage/normalization.ts';
import { serializeStorageCache } from '@core/storage/persistence/storageGroupSerialization.ts';
import { parseStorageCache } from '@core/storage/persistence/storageCacheParsing.ts';
import { normalizeStorageSyncSnapshot, serializeStorageSyncSnapshot } from '@core/storage/service/syncSnapshot.ts';
import { normalizeAccentColorPreference } from '@core/theme/accentColor.ts';
import { normalizeSurfaceColorPreference } from '@core/theme/surfaceColor.ts';
import type { StorageSyncSnapshot, StorageSyncAdapterContext, StorageSyncAdapterHandlers, StorageSyncApplySnapshotBridge } from '@core/storage/service/events/sync/types.ts';
import { type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { CrossTabPublishOutcome } from '@core/crosstab/channel.ts';

const STORAGE_CROSS_TAB_CHANNEL_ID = 'soai.webui.storage';
const STORAGE_CROSS_TAB_MESSAGE_TYPE = 'storage.snapshot';

const replaceRecordContents = (target: JsonObject, source: JsonObject): void => {
    for (const key of Object.keys(target)) {
        if (!(key in source)) {
            delete target[key];
        }
    }
    Object.assign(target, source);
};

const createStorageSyncAdapterHandlers = (context: StorageSyncAdapterContext): StorageSyncAdapterHandlers => {
    const { state, dependencies, adapters } = context;

    const getCrossTabChannel = (): { publish: (message: JsonValue | null) => CrossTabPublishOutcome; subscribe: (listener: (message: JsonValue | null) => void) => () => void; close: () => void } => {
        const stateManager = dependencies.stateManager;
        if (!isFunction(stateManager.getCrossTabChannel)) {
            throw new Error('StorageManager requires stateManager.getCrossTabChannel for cross-tab sync');
        }
        return stateManager.getCrossTabChannel(STORAGE_CROSS_TAB_CHANNEL_ID);
    };

    const scheduleBroadcast = (): void => {
        if (state.isApplyingSyncSnapshot) {
            return;
        }
        if (state.sharedBroadcastHandle !== null) {
            clearTimeout(state.sharedBroadcastHandle);
        }
        state.sharedBroadcastHandle = setTimeout(() => {
            state.sharedBroadcastHandle = null;
            void broadcast().catch((error) => {
                errorHandler.error('StorageManager', 'Broadcast failed', error);
            });
        }, 25);
    };

    const resolveIdentity = async (): Promise<string> => {
        return state.windowIdentity || (await state.windowIdentityReady);
    };

    const broadcast = async (): Promise<void> => {
        if (state.isApplyingSyncSnapshot) {
            return;
        }
        const originId = await resolveIdentity();
        if (!originId) {
            throw new Error('Identity required');
        }

        const cache = serializeStorageCache(state.cache, CROSS_TAB_SYNC_GROUPS);

        const revision = createNextCrossTabRevision(state.sharedRevision, originId);
        const snapshot: StorageSyncSnapshot = {
            origin: originId,
            revision,
            cache,
            session: adapters.clone(toJsonCompatibleObject(state.session)),
            redirectAfterLogin: state.redirectAfterLogin || null,
            isAuthenticated: state.isAuthenticated
        };
        const serializedSnapshot = serializeStorageSyncSnapshot(snapshot);
        state.sharedRevision = revision;
        dependencies.stateManager.setTabState(state.stateKey, serializedSnapshot);
        getCrossTabChannel().publish({
            type: STORAGE_CROSS_TAB_MESSAGE_TYPE,
            origin: originId,
            revision: serializeCrossTabRevision(revision),
            payload: serializedSnapshot
        });
    };

    const applySnapshot = (snapshot: StorageSyncSnapshot, snapshotBridge: StorageSyncApplySnapshotBridge): void => {
        const revision = snapshot.revision;
        if (compareCrossTabRevision(revision, state.sharedRevision) <= 0) {
            return;
        }

        const originId = snapshot.origin?.trim();
        if (originId === state.windowIdentity) {
            state.sharedRevision = revision;
            return;
        }

        state.isApplyingSyncSnapshot = true;
        try {
            const previousHiddenSidebarPages = state.cache.ui.hiddenSidebarPages.slice();
            const previousShowMainStatusIndicator = state.cache.ui.showMainStatusIndicator;
            const previousCodeRecognitionEnabled = state.cache.ui.codeRecognitionEnabled;
            const previousLanguage = state.cache.ui.language;
            const previousClockPreferences = readClockPreferenceState(state.cache.ui);
            const parsedCache = parseStorageCache(snapshot.cache, {
                clone: adapters.clone,
                createDefaults: context.createDefaults,
                internalRemoteKeys: new Set<string>(),
                normalizeLimit: adapters.normalizeLimit,
                normalizeZoom: adapters.normalizeZoom,
                preserveDefaultMisc: false,
                rejectUnknownKeys: false
            });
            Object.assign(state.cache.ui, parsedCache.ui);
            Object.assign(state.cache.logs, parsedCache.logs);
            Object.assign(state.cache.terminal, parsedCache.terminal);
            Object.assign(state.cache.search, parsedCache.search);
            Object.assign(state.cache.hardware, parsedCache.hardware);
            Object.assign(state.cache.filters, parsedCache.filters);
            Object.assign(state.cache.wizard, parsedCache.wizard);
            Object.assign(state.cache.settings, parsedCache.settings);
            replaceRecordContents(state.cache.misc, parsedCache.misc);

            const ui = state.cache.ui;
            syncLocalizationPreferencesFromUi(ui);
            ui.headerAutoHide = ui.headerAutoHide !== false;
            ui.showScrollToTopButton = ui.showScrollToTopButton !== false;
            ui.glassEnabled = ui.glassEnabled !== false;
            ui.accentColor = normalizeAccentColorPreference(ui.accentColor) ?? null;
            ui.surfaceColor = normalizeSurfaceColorPreference(ui.surfaceColor) ?? null;

            applyPresentationPreferenceDomEffects({
                preferences: ui,
                includeHeaderAutoHideClass: true,
                dispatchClockChanged: false,
                applyTheme: snapshotBridge.applyTheme,
                effects: context.effects,
                afterScrollTopActionClass: context.effects.reapplyHeaderStats
            });
            snapshotBridge.ensureMainState();

            for (const group of LOCAL_STORAGE_GROUPS) {
                snapshotBridge.syncLocal(group);
            }

            state.session = normalizeSessionData(snapshot.session);
            adapters.writeStorage('sessionStorage', state.localKeys.session, toJsonCompatibleValue(state.session));
            state.redirectAfterLogin = snapshot.redirectAfterLogin;
            state.isAuthenticated = !!snapshot.isAuthenticated;
            dependencies.stateManager.setTabState(state.stateKey, serializeStorageSyncSnapshot(snapshot));

            if (state.cache.ui.showMainStatusIndicator !== previousShowMainStatusIndicator || !arraysEqual(state.cache.ui.hiddenSidebarPages, previousHiddenSidebarPages)) {
                dispatchCustomEvent(CHANGED_EVENTS.sidebarCustomization, null);
            }
            if (state.cache.ui.codeRecognitionEnabled !== previousCodeRecognitionEnabled) {
                dispatchCustomEvent(CHANGED_EVENTS.codeRecognition, { enabled: state.cache.ui.codeRecognitionEnabled });
            }
            if (state.cache.ui.language !== previousLanguage) {
                dispatchCustomEvent(EVENT_REQUEST, { language: state.cache.ui.language });
            }
            const nextClockPreferences = readClockPreferenceState(state.cache.ui);
            if (!clockPreferenceStatesEqual(previousClockPreferences, nextClockPreferences)) {
                dispatchClockPreferenceChanged(nextClockPreferences);
            }
        } finally {
            state.sharedRevision = revision;
            state.isApplyingSyncSnapshot = false;
        }

        if (!originId) {
            snapshotBridge.scheduleBroadcast();
        }
    };

    const connectShared = async (applyTheme: StorageSyncApplySnapshotBridge['applyTheme']): Promise<void> => {
        await resolveIdentity();

        const snapshotValue = dependencies.stateManager.getTabState(state.stateKey);
        const snapshot = normalizeStorageSyncSnapshot(snapshotValue);
        if (snapshot) {
            applySnapshot(snapshot, {
                applyTheme,
                ensureMainState: context.ensureMainState,
                syncLocal: context.syncLocal,
                scheduleBroadcast
            });
        } else if (snapshotValue !== null && snapshotValue !== undefined) {
            errorHandler.warn('StorageManager', 'Ignoring invalid shared snapshot payload', snapshotValue);
        }

        if (!state.sharedSubscription) {
            const channel = getCrossTabChannel();
            state.sharedSubscription = channel.subscribe((message: JsonValue) => {
                if (!isObject(message)) {
                    return;
                }
                if (message['type'] !== STORAGE_CROSS_TAB_MESSAGE_TYPE) {
                    return;
                }
                const origin = message['origin'];
                if (isString(origin) && origin.trim() && origin.trim() === state.windowIdentity) {
                    return;
                }
                const payload = message['payload'];
                const normalized = normalizeStorageSyncSnapshot(payload ?? null);
                if (!normalized) {
                    errorHandler.warn('StorageManager', 'Ignoring invalid shared snapshot update', payload);
                    return;
                }
                applySnapshot(normalized, {
                    applyTheme,
                    ensureMainState: context.ensureMainState,
                    syncLocal: context.syncLocal,
                    scheduleBroadcast
                });
            });
        }
    };

    return {
        scheduleBroadcast,
        broadcast,
        connectShared
    };
};

export { createStorageSyncAdapterHandlers };
