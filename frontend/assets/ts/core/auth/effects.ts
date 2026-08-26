/* SoAI - Shared auth effects [frontend/assets/ts/core/auth/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { clearCsrfToken } from '@core/api/csrf.ts';
import { AUTH_TAG } from '@core/auth/constants.ts';
import { isSessionInvalidApiError } from '@core/auth/sessionFailure.ts';
import type { AuthManagerServiceResolver, AuthManagerStateHandle } from '@core/auth/internalContracts.ts';
import type { InitializeOptions, SessionInvalidationResult, WebuiUser, WizardStatus } from '@core/auth/types.ts';
import { connectSharedState } from '@core/auth/sharedState.ts';
import { addCallback, applyUserSession, beginAuthenticatedEpoch, buildSessionPayload, clearSession, notifyLogin, notifyLogout, serializeUser } from '@core/auth/state.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isDetailedWizardStatus } from '@core/api/contracts/wizardLicensingContracts.ts';

const initializeAuthManager = async (state: AuthManagerStateHandle, resolveApi: AuthManagerServiceResolver['resolveApi'], resolveStorage: AuthManagerServiceResolver['resolveStorage'], runAuthTransition: <T>(operation: () => Promise<T>) => Promise<T>, options: InitializeOptions = {}): Promise<boolean | undefined> => {
    await connectSharedState(
        state,
        {
            notifyLogin,
            notifyLogout,
            persistLogin: async (user) => {
                const storage = await resolveStorage();
                const session = buildSessionPayload(user);
                if (session) {
                    storage.setSession(session);
                }
                await storage.setAuthenticated(true, { authTransitionOwned: true });
            },
            persistLogout: async () => {
                const storage = await resolveStorage();
                storage.clearSession();
                await storage.setAuthenticated(false, { authTransitionOwned: true });
            },
            probeAuthenticatedUser: async (announcement) => {
                const api = await resolveApi();
                const user = await api.webui.auth.getMe({ authTransitionOwned: true });
                return user.id === announcement.id ? user : null;
            }
        },
        serializeUser,
        runAuthTransition
    );
    if (options?.wizardState) {
        state.wizardStatusSnapshot = options.wizardState;
    }
    if (options.skipSessionProbe === true) {
        await clearSession(state, resolveStorage);
        return false;
    }
    try {
        const api = await resolveApi();
        const user = await api.webui.auth.getMe({ authTransitionOwned: true });
        const epoch = beginAuthenticatedEpoch(state);
        const wasSessionStored = await applyUserSession(state, user, resolveStorage, undefined, epoch);
        return wasSessionStored;
    } catch (error) {
        const err = ensureError(error);
        if (isSessionInvalidApiError(err)) {
            await clearSession(state, resolveStorage);
            return false;
        }
        errorHandler.warn(AUTH_TAG, 'Initialization failed', err);
    }
    return undefined;
};

const runSessionInvalidation = async (state: AuthManagerStateHandle, resolveStorage: AuthManagerServiceResolver['resolveStorage'], revokeServerSession: (() => Promise<void>) | null): Promise<SessionInvalidationResult> => {
    const activeInvalidation = state.sessionInvalidationPromise;
    if (activeInvalidation !== null) {
        return activeInvalidation;
    }
    state.isLoggingOut = true;
    const invalidation = (async (): Promise<SessionInvalidationResult> => {
        const serverRevocation = revokeServerSession?.().catch((error) => {
            errorHandler.warn(AUTH_TAG, 'Server session revocation failed after local sign-out', ensureError(error));
        });
        clearCsrfToken();
        await clearSession(state, resolveStorage);
        const storage = await resolveStorage();
        storage.clearRedirectAfterLogin();
        await serverRevocation;
        return { status: 'signedOut' };
    })();
    state.sessionInvalidationPromise = invalidation;
    try {
        return await invalidation;
    } finally {
        if (state.sessionInvalidationPromise === invalidation) {
            state.sessionInvalidationPromise = null;
            state.isLoggingOut = false;
        }
    }
};

const invalidateSessionAuthManager = async (state: AuthManagerStateHandle, resolveStorage: AuthManagerServiceResolver['resolveStorage']): Promise<SessionInvalidationResult> => runSessionInvalidation(state, resolveStorage, null);

const logoutAuthManager = async (state: AuthManagerStateHandle, resolveApi: AuthManagerServiceResolver['resolveApi'], resolveStorage: AuthManagerServiceResolver['resolveStorage']): Promise<SessionInvalidationResult> => {
    if (!state.isAuthenticated) {
        return { status: 'signedOut' };
    }
    try {
        return await runSessionInvalidation(state, resolveStorage, async (): Promise<void> => {
            const api = await resolveApi();
            await api.webui.auth.logout();
        });
    } catch (error) {
        const err = ensureError(error);
        errorHandler.error(AUTH_TAG, 'Logout failed', err);
        throw err;
    }
};

const checkWizardStatus = async (state: AuthManagerStateHandle, resolveApi: AuthManagerServiceResolver['resolveApi']): Promise<boolean> => {
    try {
        const api = await resolveApi();
        const lookup = await api.webui.wizard.status();
        state.wizardStatusSnapshot = isDetailedWizardStatus(lookup) ? lookup : null;
        return lookup.setupNeeded;
    } catch (error) {
        const err = ensureError(error);
        errorHandler.error(AUTH_TAG, 'Wizard status lookup failed', err);
        throw ensureError(err);
    }
};

const getWizardStatusSnapshot = (state: AuthManagerStateHandle): WizardStatus | null => (state.wizardStatusSnapshot ? { ...state.wizardStatusSnapshot } : null);

const onAuthLogin = (state: AuthManagerStateHandle, callback: (user: WebuiUser | null) => void | Promise<void>): (() => void) => addCallback(state.loginCallbacks, callback);

const onAuthLogout = (state: AuthManagerStateHandle, callback: () => void | Promise<void>): (() => void) => addCallback(state.logoutCallbacks, callback);

export { checkWizardStatus, getWizardStatusSnapshot, initializeAuthManager, invalidateSessionAuthManager, logoutAuthManager, notifyLogin, notifyLogout, onAuthLogin, onAuthLogout };
