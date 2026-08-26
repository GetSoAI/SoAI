/* SoAI - Shared storage service contracts [frontend/assets/ts/core/storage/service/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { CrossTabRevision } from '@core/crosstab/revision.ts';
import type { CrossTabPublishOutcome } from '@core/crosstab/channel.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { StorageLocalKeys } from '@core/storage/keys.ts';
import type { SessionData, StorageCache, StorageType, SyncGroup } from '@core/storage/types.ts';

interface ThemeApplyOptions {
    persist?: boolean | undefined;
    update?: boolean | undefined;
}

interface StorageAdapters {
    clone: <T>(value: T) => T;
    initializeStorageAvailability: () => void;
    readStorage: (storageType: StorageType, key: string) => JsonValue | null | undefined;
    writeStorage: (storageType: StorageType, key: string, value: JsonValue | null | undefined) => void;
    normalizeLimit: (limit: number) => number;
    normalizeZoom: (zoom: number, min: number, max: number) => number;
    serialize: (value: JsonValue | null | undefined) => string;
}

interface StorageRuntimeEvents {
    syncLocal: (group: string) => void;
    queuePersist: (group: string) => Promise<JsonValue | null>;
    flushPending: () => Promise<void>;
    mergeRemote: (remote: JsonObject | null | undefined) => void;
    refreshChatPreferences: (options?: { authTransitionOwned?: boolean }) => Promise<JsonObject>;
    persistChatPreferencePatch: (patch: JsonObject) => Promise<JsonObject>;
    prepareChatPreferencePatch: (patch: JsonObject) => () => Promise<JsonObject>;
    prepareExternalChatPreferenceProjection: () => (patch: JsonObject) => Promise<void>;
    prepareChatPreferenceInvalidation: () => () => CrossTabPublishOutcome | null;
    pendingConversationDefaults: () => JsonObject;
    scheduleBroadcast: () => void;
    applyTheme: (preference: string, options?: ThemeApplyOptions) => string;
    ensureMainState: () => void;
    ready: Promise<void>;
}

interface StorageRuntimeEventDependencies {
    state: StorageRuntimeState;
    dependencies: StorageRuntimeDependencies;
    createDefaults: () => StorageCache;
    adapters: StorageAdapters;
    effects: StorageUiEffects;
}

interface StorageUiEffects {
    bodyClass: (className: string, enabled: boolean) => void;
    setGlassDisabled: (disabled: boolean) => void;
    setAttr: (name: string, value: string) => void;
    reapplyHeaderStats: () => void;
}

interface StorageApiClientContract {
    webui?: {
        preferences?: {
            get?: (options?: { authTransitionOwned?: boolean }) => Promise<JsonValue | null>;
            update?: (payload: JsonObject) => Promise<ApiResponsePayload>;
        };
    };
}

interface TabStateManagerContract {
    subscribeTabState: (callback: (event: { key?: string; remote?: boolean; value?: JsonValue | null }) => void) => () => void;
    getTabState: (key: string, defaultValue?: JsonValue | null) => JsonValue | null;
    setTabState: (key: string, value: JsonValue | null) => void;
    getCrossTabChannel: (channelId: string) => {
        publish: (message: JsonValue | null) => CrossTabPublishOutcome;
        subscribe: (listener: (message: JsonValue | null) => void) => () => void;
        close: () => void;
    };
}

interface StorageRuntimeState {
    defaults: StorageCache;
    cache: StorageCache;
    pendingGroups: Set<string>;
    writeQueue: Promise<JsonValue | null>;
    windowIdentity: string | null;
    windowIdentityReady: Promise<string>;
    isAuthenticated: boolean;
    session: SessionData;
    stateKey: string;
    sharedRevision: CrossTabRevision | null;
    persistedChecksums: Record<string, string>;
    inflightChecksums: Record<string, string>;
    queuedChecksums: Record<string, string>;
    resources: ResourceTracker;
    localKeys: StorageLocalKeys;
    localStorageAvailable: boolean;
    sessionStorageAvailable: boolean;
    maintenanceHold: boolean;
    sharedSubscription?: () => void;
    systemThemeListener?: MediaQueryList;
    isApplyingSyncSnapshot?: boolean;
    sharedBroadcastHandle: ReturnType<typeof setTimeout> | null;
    redirectAfterLogin?: string | null;
}

interface StorageRuntimeDependencies {
    apiClient: StorageApiClientContract;
    stateManager: TabStateManagerContract;
}

interface StorageRuntime {
    state: StorageRuntimeState;
    ready: Promise<void>;
    clone: <T>(value: T) => T;
    createDefaults: () => StorageCache;
    writeStorage: (storageType: StorageType, key: string, value: JsonValue | null | undefined) => void;
    queuePersist: (group: string) => Promise<JsonValue | null>;
    flushPending: () => Promise<void>;
    mergeRemote: (remote: JsonObject | null | undefined) => void;
    refreshChatPreferences: (options?: { authTransitionOwned?: boolean }) => Promise<JsonObject>;
    persistChatPreferencePatch: (patch: JsonObject) => Promise<JsonObject>;
    prepareChatPreferencePatch: (patch: JsonObject) => () => Promise<JsonObject>;
    prepareExternalChatPreferenceProjection: () => (patch: JsonObject) => Promise<void>;
    prepareChatPreferenceInvalidation: () => () => CrossTabPublishOutcome | null;
    pendingConversationDefaults: () => JsonObject;
    syncLocal: (group: string) => void;
    scheduleBroadcast: () => void;
    applyTheme: (preference: string, options?: ThemeApplyOptions) => string;
    bodyClass: (className: string, enabled: boolean) => void;
    setGlassDisabled: (disabled: boolean) => void;
    setAttr: (name: string, value: string) => void;
    reapplyHeaderStats: () => void;
    normalizeLimit: (limit: number) => number;
    normalizeZoom: (zoom: number, min: number, max: number) => number;
    ensureMainState: () => void;
}

interface StorageKeyBinding {
    get: (defaultValue?: JsonValue | null) => JsonValue | null;
    set: (value: JsonValue | null) => void;
    syncGroup?: SyncGroup | undefined;
}

export type { StorageApiClientContract, StorageRuntimeDependencies, StorageRuntime, StorageRuntimeState, StorageKeyBinding, TabStateManagerContract, ThemeApplyOptions, StorageAdapters, StorageRuntimeEvents, StorageRuntimeEventDependencies, StorageUiEffects };
