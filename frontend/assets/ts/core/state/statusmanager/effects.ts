/* SoAI - Shared state status manager effects [frontend/assets/ts/core/state/statusmanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { applyBackendPayload } from '@core/state/statusmanager/actions.ts';
import type { ApiClient, AuthService, BackendPayload, StreamManager } from '@core/state/statusmanager/contracts.ts';
import { bindAuthEvents, startStatusStreamMonitor } from '@core/state/statusmanager/events.ts';
import { isStreamManager, readStatusFromPayload } from '@core/state/statusmanager/mappers.ts';
import type { ErrorLogger, StreamMonitorResult, StatusManagerState } from '@core/state/statusmanager/internalContracts.ts';
import type { StatusInput } from '@core/state/statusTypes.ts';
import type { ErrorHandler } from '@core/state/types.ts';
import { hasFunctionProperty, isFunction, isObject } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

const resolveStreamManager = (streamManagerProvider: () => StreamManager): StreamManager => {
    const candidate = streamManagerProvider();
    if (!isStreamManager(candidate)) {
        throw new Error('Stream manager must provide getResource and subscribeResourceState');
    }
    return candidate;
};

const createStatusStreamMonitor = ({ streamManagerProvider, statusStreamId, onStatus, onError }: { streamManagerProvider: () => StreamManager; statusStreamId: string; onStatus: (status: StatusInput) => void; onError: ErrorLogger }): StreamMonitorResult => {
    return startStatusMonitor({
        streamManager: resolveStreamManager(streamManagerProvider),
        streamId: statusStreamId,
        onStatus,
        onError
    });
};

const startStatusMonitor = ({ streamManager, streamId, onStatus, onError }: { streamManager: StreamManager; streamId: string; onStatus: (status: StatusInput) => void; onError: ErrorLogger }): StreamMonitorResult => {
    return startStatusStreamMonitor({
        streamManager,
        streamId,
        handler: ({ rawValue }) => {
            onStatus(readStatusFromPayload(rawValue));
        },
        onError
    });
};

const loadDefinitionsFromApi = async ({ apiClientProvider, reportError }: { apiClientProvider: () => Promise<ApiClient | null>; reportError: ErrorLogger }): Promise<BackendPayload | null> => {
    const api = await apiClientProvider();
    if (!api || !isFunction(api.system?.stateDefinitions)) {
        return null;
    }
    try {
        return await api.system.stateDefinitions();
    } catch (error) {
        const runtimeError = ensureError(error);
        reportError('StatusManager', 'State definitions refresh failed', runtimeError);
        throw runtimeError;
    }
};

const refreshDefinitionsFromBackend = async ({ state, isAuthenticated, apiClientProvider, getDefinitionsPromise, setDefinitionsPromise, reportError }: { state: StatusManagerState; isAuthenticated: () => boolean; apiClientProvider: () => Promise<ApiClient | null>; getDefinitionsPromise: () => Promise<StatusManagerState['definitions']> | null; setDefinitionsPromise: (next: Promise<StatusManagerState['definitions']> | null) => void; reportError: ErrorLogger }): Promise<StatusManagerState['definitions']> => {
    if (!isAuthenticated()) {
        return Promise.resolve(state.definitions);
    }
    const existing = getDefinitionsPromise();
    if (existing) {
        return existing;
    }

    const next = (async (): Promise<StatusManagerState['definitions']> => {
        try {
            const payload = await loadDefinitionsFromApi({
                apiClientProvider,
                reportError
            });
            if (payload) {
                applyBackendPayload(state, payload);
            }
        } finally {
            setDefinitionsPromise(null);
        }
        return state.definitions;
    })();
    setDefinitionsPromise(next);
    return next;
};

const assertAuthContract = <T>(auth: T): auth is T & AuthService => {
    if (!isObject(auth)) {
        throw new Error('Auth service must be available');
    }
    if (!hasFunctionProperty(auth, 'onLogin') || !hasFunctionProperty(auth, 'onLogout')) {
        throw new Error('Auth service must expose onLogin and onLogout');
    }
    if (!('isAuthenticated' in auth) || typeof auth.isAuthenticated !== 'boolean') {
        throw new Error('Auth service must expose isAuthenticated state');
    }
    return true;
};

const initializeAuthIntegration = async ({ authServiceProvider, stateErrorHandler, resources, onLogin, onLogout }: { authServiceProvider: () => Promise<AuthService>; stateErrorHandler: ErrorHandler; resources: ResourceTracker; onLogin: () => void; onLogout: () => void }): Promise<{ auth: AuthService }> => {
    try {
        const auth = await authServiceProvider();
        assertAuthContract(auth);
        bindAuthEvents({
            auth,
            resources,
            onLogin,
            onLogout,
            onError: (error) => {
                const logger = stateErrorHandler.warn || errorHandler.warn;
                if (logger) {
                    logger('StatusManager', 'Auth event subscription failed', error);
                }
            }
        });
        return { auth };
    } catch (error) {
        const runtimeError = ensureError(error);
        const logger = stateErrorHandler.error || errorHandler.error;
        if (logger) {
            logger('StatusManager', 'Auth service resolution failed', runtimeError);
        }
        throw runtimeError;
    }
};

export { createStatusStreamMonitor, initializeAuthIntegration, refreshDefinitionsFromBackend };
