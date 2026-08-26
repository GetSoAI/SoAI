/* SoAI - Shared auth state [frontend/assets/ts/core/auth/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { createModuleLogger } from '@core/moduleContext.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { AUTH_TAG } from '@core/auth/constants.ts';
import type { AuthCallback, LoginCallback, WebuiUser, WizardStatus } from '@core/auth/types.ts';
import type { AuthManagerServiceResolver, AuthManagerStateHandle } from '@core/auth/internalContracts.ts';
import { buildSessionPayload, extractUserFields, serializeUser } from '@core/auth/stateMappers.ts';
import { publishSharedState, resetAuthSharedState, safeSetStorageAuthenticated, type SharedStateHooks } from '@core/auth/sharedState.ts';
import { ensureError } from '@core/errors/coerce.ts';

const log = createModuleLogger(AUTH_TAG, { defaultLevel: 'warn' });
type UserSerializer = (value: WebuiUser) => Promise<WebuiUser>;

const createAuthManagerState = (stateKey: string): AuthManagerStateHandle => ({
    user: null,
    isAuthenticated: false,
    loginCallbacks: [],
    logoutCallbacks: [],
    stateKey,
    stateManager: null,
    stateSubscription: null,
    stateRevision: null,
    stateConnectPromise: null,
    sharedStateCommitTask: null,
    sharedStateGeneration: 0,
    isApplyingSharedState: false,
    isLoggingOut: false,
    sessionInvalidationPromise: null,
    wizardStatusSnapshot: null,
    authEpoch: 0,
    terminalEpoch: null
});

const resetAuthManagerState = (state: AuthManagerStateHandle): void => {
    state.user = null;
    state.isAuthenticated = false;
    state.loginCallbacks.length = 0;
    state.logoutCallbacks.length = 0;
    resetAuthSharedState(state);
    state.isLoggingOut = false;
    state.sessionInvalidationPromise = null;
    state.wizardStatusSnapshot = null;
    state.authEpoch += 1;
    state.terminalEpoch = state.authEpoch;
};

const beginAuthenticatedEpoch = (state: AuthManagerStateHandle): number => {
    state.authEpoch += 1;
    state.terminalEpoch = null;
    return state.authEpoch;
};

const beginTerminalAuthIntent = (state: AuthManagerStateHandle): number => {
    state.authEpoch += 1;
    state.terminalEpoch = state.authEpoch;
    state.isLoggingOut = true;
    return state.authEpoch;
};

const canApplyAuthenticatedEpoch = (state: AuthManagerStateHandle, epoch: number): boolean => state.authEpoch === epoch && state.terminalEpoch === null;

const sharedStateHooks = (): SharedStateHooks => {
    return {
        notifyLogin: (state) => notifyLogin(state),
        notifyLogout: (state) => notifyLogout(state),
        persistLogin: async (_user) => {},
        persistLogout: async () => {},
        probeAuthenticatedUser: async () => null
    };
};
const setStorageAuthenticated = async (resolveStorage: AuthManagerServiceResolver['resolveStorage'], value: boolean): Promise<void> => {
    await safeSetStorageAuthenticated(resolveStorage, value);
};
const applyUserSession = async (state: AuthManagerStateHandle, user: WebuiUser | null, resolveStorage: AuthManagerServiceResolver['resolveStorage'], serialize: UserSerializer = serializeUser, expectedEpoch: number | null = null): Promise<boolean> => {
    if (expectedEpoch !== null && !canApplyAuthenticatedEpoch(state, expectedEpoch)) {
        return false;
    }
    if (!user || !isObject(user) || !user.username) {
        await clearSession(state, resolveStorage, serialize);
        return false;
    }
    const session = buildSessionPayload(user);
    if (session) {
        try {
            const storage = await resolveStorage();
            storage?.setSession?.(session);
        } catch (error) {
            const err = ensureError(error);
            errorHandler.warn(AUTH_TAG, 'Persisting session failed', err);
        }
    }
    if (expectedEpoch !== null && !canApplyAuthenticatedEpoch(state, expectedEpoch)) {
        return false;
    }
    await setStorageAuthenticated(resolveStorage, true);
    if (expectedEpoch !== null && !canApplyAuthenticatedEpoch(state, expectedEpoch)) {
        return false;
    }
    state.user = user;
    state.isAuthenticated = true;
    try {
        await publishSharedState(state, sharedStateHooks(), serialize, expectedEpoch);
    } catch (error) {
        errorHandler.warn(AUTH_TAG, 'Publishing authenticated session state failed', ensureError(error));
    }
    if (expectedEpoch !== null && !canApplyAuthenticatedEpoch(state, expectedEpoch)) {
        return false;
    }
    await notifyLogin(state);
    return true;
};
const clearSession = async (state: AuthManagerStateHandle, resolveStorage: AuthManagerServiceResolver['resolveStorage'], serialize: UserSerializer = serializeUser): Promise<boolean> => {
    const wasAuthenticated = state.isAuthenticated;
    state.user = null;
    state.isAuthenticated = false;
    try {
        const storage = await resolveStorage();
        storage?.clearSession?.();
    } catch (error) {
        const err = ensureError(error);
        errorHandler.warn(AUTH_TAG, 'Clearing session failed', err);
    }
    await setStorageAuthenticated(resolveStorage, false);
    await publishSharedState(state, sharedStateHooks(), serialize);
    if (wasAuthenticated) {
        await notifyLogout(state);
    }
    return false;
};
const addCallback = <T extends AuthCallback | LoginCallback>(callbacks: T[], callback: T): (() => void) => {
    if (!isFunction(callback)) {
        return () => {};
    }
    callbacks.push(callback);
    return () => {
        const callbackIndex = callbacks.indexOf(callback);
        if (callbackIndex > -1) callbacks.splice(callbackIndex, 1);
    };
};
const notifyLogin = async (state: AuthManagerStateHandle): Promise<void> => {
    await Promise.allSettled(
        state.loginCallbacks.map(async (callback) => {
            try {
                await Promise.resolve(callback(state.user));
            } catch (error) {
                const err = ensureError(error);
                log('error', 'Auth callback error', err);
            }
        })
    );
};
const notifyLogout = async (state: AuthManagerStateHandle): Promise<void> => {
    await Promise.allSettled(
        state.logoutCallbacks.map(async (callback) => {
            try {
                await Promise.resolve(callback());
            } catch (error) {
                const err = ensureError(error);
                log('error', 'Auth callback error', err);
            }
        })
    );
};
const getWizardStatusSnapshot = (state: AuthManagerStateHandle): WizardStatus | null => (state.wizardStatusSnapshot ? { ...state.wizardStatusSnapshot } : null);

export { applyUserSession, beginAuthenticatedEpoch, beginTerminalAuthIntent, canApplyAuthenticatedEpoch, clearSession, createAuthManagerState, extractUserFields, getWizardStatusSnapshot, addCallback, buildSessionPayload, notifyLogin, notifyLogout, resetAuthManagerState, serializeUser, setStorageAuthenticated };
