/* SoAI - Frontend application service adapters [frontend/assets/ts/app/bootstrap/serviceconstruction/serviceAdapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { WizardStatus } from '@core/auth/types.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import type { AuthManagerContract, StateServiceInterface } from '@core/realtime/streammanager/types.ts';
import type { StorageApiClientContract, TabStateManagerContract } from '@core/storage/service/types.ts';
import { isBoolean, isFiniteNumber, isNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface StreamAuthUser {
    id?: string | number | undefined;
    username: string;
    isAdmin: boolean;
    workspacePath?: string | undefined;
    workspacePathResolved?: string | undefined;
}

interface StorageApiSource {
    webui?: {
        preferences?: {
            get?: (options?: { authTransitionOwned?: boolean }) => Promise<ApiResponsePayload>;
            update?: (payload: JsonObject) => Promise<ApiResponsePayload>;
        };
    };
}

interface RouterStateSource {
    section: {
        cleanup: () => void;
        initialize: () => void;
    };
    setTabState: (key: string, value: JsonValue | null | undefined) => void;
}

interface RouterStateAdapter {
    section: RouterStateSource['section'];
    setTabState: (key: string, value: JsonValue | null | undefined) => void;
}

interface ModalSizeState {
    width: number;
    height: number;
}

interface ModalSavedState {
    size?: ModalSizeState | undefined;
}

const createStreamStateService = (stateManager: { getTabState: (key: string, defaultValue?: JsonValue | null) => JsonValue | null | undefined; setTabState: (key: string, value: JsonValue | null | undefined) => void }): StateServiceInterface => ({
    getTabState: (key) => {
        const value = stateManager.getTabState(key, null);
        return isJsonValue(value) ? value : null;
    },
    setTabState: (key, value) => {
        stateManager.setTabState(key, value);
    }
});

const toAuthUserJson = (user: StreamAuthUser | null): JsonObject | null => {
    if (!user) return null;
    const username = user['username'];
    const isAdmin = user.isAdmin;
    if (!isString(username) || !isBoolean(isAdmin)) return null;
    const normalized: JsonObject = { username, isAdmin };
    const id = user['id'];
    if (isString(id) || isNumber(id)) normalized['id'] = id;
    const workspacePath = user.workspacePath;
    if (isString(workspacePath)) normalized['workspacePath'] = workspacePath;
    const workspacePathResolved = user.workspacePathResolved;
    if (isString(workspacePathResolved)) normalized['workspacePathResolved'] = workspacePathResolved;
    return normalized;
};

const toWizardStatusJson = (status: WizardStatus | JsonValue | null | undefined): JsonObject | null => {
    if (!status) return null;
    if (isJsonObject(status)) return status;
    const candidate = toJsonCompatibleValue(status);
    return isJsonObject(candidate) ? candidate : null;
};

const createStreamAuthService = (authManager: { isAuthenticated: boolean; onLogin: (callback: (user: StreamAuthUser | null) => void | Promise<void>) => (() => void) | void; getWizardStatusSnapshot?: () => WizardStatus | JsonValue | null }): AuthManagerContract => ({
    get isAuthenticated(): boolean {
        return authManager.isAuthenticated;
    },
    onLogin: (callback) => authManager.onLogin((user) => callback(toAuthUserJson(user))),
    getWizardStatusSnapshot: () => {
        return toWizardStatusJson(authManager.getWizardStatusSnapshot?.());
    }
});

const createStorageApiService = (apiClient: StorageApiSource): StorageApiClientContract => ({
    webui: {
        preferences: {
            get: async (options) => {
                const payload = await apiClient.webui?.preferences?.get?.(options);
                return isJsonValue(payload) ? payload : null;
            },
            update: (payload) => {
                const update = apiClient.webui?.preferences?.update;
                if (!update) {
                    throw new Error('Storage preferences update API is unavailable');
                }
                return update(payload);
            }
        }
    }
});

const createStorageStateService = (stateManager: { subscribeTabState: (callback: (event: { key: string; remote: boolean; value: JsonValue | null | undefined }) => void) => () => void; getTabState: (key: string, defaultValue?: JsonValue | null) => JsonValue | null | undefined; setTabState: (key: string, value: JsonValue | null | undefined) => void; getCrossTabChannel: (channelId: string) => { publish: (message: JsonValue | null) => 'published' | 'queued'; subscribe: (listener: (message: JsonValue | null | undefined) => void) => () => void; close: () => void } }): TabStateManagerContract => ({
    subscribeTabState: (callback) =>
        stateManager.subscribeTabState((event) => {
            callback({
                key: event.key,
                remote: event.remote,
                value: isJsonValue(event.value) ? event.value : null
            });
        }),
    getTabState: (key, defaultValue = null) => {
        const value = stateManager.getTabState(key, defaultValue);
        return isJsonValue(value) ? value : null;
    },
    setTabState: (key, value) => {
        stateManager.setTabState(key, value);
    },
    getCrossTabChannel: (channelId) => {
        const channel = stateManager.getCrossTabChannel(channelId);
        return {
            publish: (message) => {
                return channel.publish(message);
            },
            subscribe: (listener) =>
                channel.subscribe((message) => {
                    listener(isJsonValue(message) ? message : null);
                }),
            close: () => {
                channel.close();
            }
        };
    }
});

const createRouterStateService = (stateManager: RouterStateSource): RouterStateAdapter => ({
    section: stateManager.section,
    setTabState: (key, value) => {
        stateManager.setTabState(key, isJsonValue(value) ? value : null);
    }
});

const normalizeModalSavedState = (value: JsonObject | null): ModalSavedState | null => {
    const size = value?.['size'];
    if (!isJsonObject(size)) {
        return null;
    }
    const width = size['width'];
    const height = size['height'];
    if (!isFiniteNumber(width) || !isFiniteNumber(height)) {
        return null;
    }
    return { size: { width, height } };
};

const createModalStorageService = (storage: { getModalState: (id: string) => JsonObject | null; setModalState: (id: string, state: JsonObject) => void }): { getModalState: (id: string) => ModalSavedState | null; setModalState: (id: string, state: ModalSavedState) => void } => ({
    getModalState: (id: string): ModalSavedState | null => normalizeModalSavedState(storage.getModalState(id)),
    setModalState: (id: string, state: ModalSavedState): void => {
        const size = state.size;
        const payload: JsonObject = {};
        if (size) {
            payload['size'] = { width: size.width, height: size.height };
        }
        storage.setModalState(id, payload);
    }
});

export { createModalStorageService, createRouterStateService, createStorageApiService, createStorageStateService, createStreamAuthService, createStreamStateService };
