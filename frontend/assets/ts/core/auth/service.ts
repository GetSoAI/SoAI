/* SoAI - Shared authentication service [frontend/assets/ts/core/auth/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { checkWizardStatus, getWizardStatusSnapshot, initializeAuthManager, invalidateSessionAuthManager, logoutAuthManager, notifyLogin, notifyLogout, onAuthLogin, onAuthLogout } from '@core/auth/effects.ts';
import { loginAuthManager } from '@core/auth/loginEffects.ts';
import { reconcileWizardCompletion } from '@core/auth/wizardCompletion.ts';
import { getLanguageService } from '@core/languageservice/service.ts';
import { applyUserSession, beginAuthenticatedEpoch, beginTerminalAuthIntent, createAuthManagerState, resetAuthManagerState } from '@core/auth/state.ts';
import { isApiInterface, isStorageInterface } from '@core/auth/adapters.ts';
import { AUTH_TAG, STATE_KEY } from '@core/auth/constants.ts';
import type { ApiInterface, AuthCallback, InitializeOptions, LoginCallback, LoginResult, SessionInvalidationResult, StorageInterface, WebuiUser, WizardCompletionResult, WizardStatus } from '@core/auth/types.ts';
import type { AuthManagerStateHandle } from '@core/auth/internalContracts.ts';
import { getApiClient } from '@core/api/service.ts';
import { requireStorageService } from '@core/storage/runtime.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { AuthTransitionOwner, AuthTransitionUnavailableError } from '@core/auth/transitionOwner.ts';
import { i18n } from '@core/i18n/index.ts';
import type { IdentityMutationSuccess } from '@core/api/contracts/webuiIdentityMutationContracts.ts';
import { compareWebuiUserRevision } from '@core/users/userRevision.ts';
import type { InitiatedIdentityMutationRequest } from '@core/auth/identityMutationRecovery.ts';
import { AuthRecoverySupervisor } from '@core/auth/recoverySupervisor.ts';
import { APIError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { runProtectedReadGate } from '@core/auth/protectedReadGate.ts';

class AuthManager {
    #state: AuthManagerStateHandle;
    #api: ApiInterface | null = null;
    #storage: StorageInterface | null = null;
    #resolverApi: (() => Promise<ApiInterface>) | null = null;
    #resolverStorage: (() => Promise<StorageInterface>) | null = null;
    readonly #transitions = new AuthTransitionOwner();
    #terminalTask: Promise<SessionInvalidationResult> | null = null;
    #recoveryAbortController = new AbortController();
    readonly #recovery = new AuthRecoverySupervisor();

    constructor() {
        this.#state = createAuthManagerState(STATE_KEY);
    }

    get user(): WebuiUser | null {
        return this.#state.user;
    }

    get isAuthenticated(): boolean {
        return this.#state.isAuthenticated;
    }

    get loginCallbacks(): LoginCallback[] {
        return this.#state.loginCallbacks;
    }

    get logoutCallbacks(): AuthCallback[] {
        return this.#state.logoutCallbacks;
    }

    #resolveApi(): () => Promise<ApiInterface> {
        if (this.#resolverApi) return this.#resolverApi;
        const resolver = async (): Promise<ApiInterface> => {
            if (this.#api) return this.#api;
            const resolved = getApiClient();
            if (!isApiInterface(resolved)) {
                throw new Error('API client is unavailable');
            }
            resolved.setAuthTransitionGate(async (): Promise<void> =>
                runProtectedReadGate({
                    state: this.#state,
                    transitions: this.#transitions,
                    recovery: this.#recovery,
                    resolveApi: this.#resolveApi(),
                    resolveStorage: this.#resolveStorage(),
                    signal: this.#recoveryAbortController.signal,
                    reconcile: async (user) => this.#reconcileAuthenticatedUser(user, this.#state.authEpoch, this.#resolveStorage())
                })
            );
            this.#api = resolved;
            return resolved;
        };
        this.#resolverApi = resolver;
        return resolver;
    }

    #resolveStorage(): () => Promise<StorageInterface> {
        if (this.#resolverStorage) return this.#resolverStorage;
        const resolver = async (): Promise<StorageInterface> => {
            if (this.#storage) return this.#storage;
            const resolved = requireStorageService();
            if (!isStorageInterface(resolved)) {
                throw new Error('Storage manager is unavailable');
            }
            this.#storage = resolved;
            return resolved;
        };
        this.#resolverStorage = resolver;
        return resolver;
    }

    #createAuthResolvers(): readonly [() => Promise<ApiInterface>, () => Promise<StorageInterface>] {
        return [this.#resolveApi(), this.#resolveStorage()];
    }

    async initialize(_options: InitializeOptions = {}): Promise<boolean | undefined> {
        const [resolveApi, resolveStorage] = this.#createAuthResolvers();
        return await this.#transitions.runCookieMutation(async () => {
            const initialized = await initializeAuthManager(this.#state, resolveApi, resolveStorage, (operation) => this.#transitions.runCookieMutation(operation), _options);
            const actor = this.#state.user;
            if (initialized === true && actor !== null) {
                try {
                    const result = await this.#recovery.resume(actor, await resolveApi(), await resolveStorage(), this.#recoveryAbortController.signal);
                    if (result !== null) await this.#reconcileAuthenticatedUser(result.user, this.#state.authEpoch, resolveStorage);
                } catch (error) {
                    const runtimeError = ensureError(error);
                    if (runtimeError instanceof APIError && runtimeError.status === 401) {
                        beginTerminalAuthIntent(this.#state);
                        await invalidateSessionAuthManager(this.#state, resolveStorage);
                        return false;
                    }
                    errorHandler.warn(AUTH_TAG, 'Persisted identity mutation recovery remains unresolved', runtimeError);
                }
            }
            return initialized;
        });
    }

    async login(username: string, password: string): Promise<LoginResult> {
        const [resolveApi, resolveStorage] = this.#createAuthResolvers();
        try {
            return await this.#transitions.runCookieMutation(async (): Promise<LoginResult> => {
                const epoch = beginAuthenticatedEpoch(this.#state);
                const result = await loginAuthManager(this.#state, username, password, resolveApi, resolveStorage, epoch);
                if (result.status === 'authenticated') this.#recovery.reset();
                return result;
            });
        } catch (error) {
            if (error instanceof AuthTransitionUnavailableError) {
                return { status: 'rejected', error: i18n.t('login.errors.loginFailed') };
            }
            throw error;
        }
    }

    async logout(): Promise<SessionInvalidationResult> {
        const [resolveApi, resolveStorage] = this.#createAuthResolvers();
        return await this.#runTerminalTransition(async () => logoutAuthManager(this.#state, resolveApi, resolveStorage));
    }

    async invalidateSession(): Promise<SessionInvalidationResult> {
        const [, resolveStorage] = this.#createAuthResolvers();
        return await this.#runTerminalTransition(async () => invalidateSessionAuthManager(this.#state, resolveStorage));
    }

    async completeWizard(username: string, password: string): Promise<WizardCompletionResult> {
        const [resolveApi, resolveStorage] = this.#createAuthResolvers();
        try {
            return await this.#transitions.runCookieMutation(async (): Promise<WizardCompletionResult> => {
                const epoch = beginAuthenticatedEpoch(this.#state);
                const result = await reconcileWizardCompletion(this.#state, username, password, getLanguageService().getLanguage(), resolveApi, resolveStorage, async (state: AuthManagerStateHandle, loginUsername: string, loginPassword: string, apiResolver: () => Promise<ApiInterface>, storageResolver: () => Promise<StorageInterface>, expectedEpoch: number): Promise<LoginResult> => loginAuthManager(state, loginUsername, loginPassword, apiResolver, storageResolver, expectedEpoch), epoch);
                if (result.status === 'authenticated') this.#recovery.reset();
                return result;
            });
        } catch (error) {
            if (error instanceof AuthTransitionUnavailableError) {
                return { status: 'rejected', error: i18n.t('login.errors.loginFailed') };
            }
            throw error;
        }
    }

    async runOwnIdentityMutation(request: InitiatedIdentityMutationRequest): Promise<IdentityMutationSuccess> {
        const [, resolveStorage] = this.#createAuthResolvers();
        return await this.#transitions.runCookieMutation(async (): Promise<IdentityMutationSuccess> => {
            const epoch = this.#state.authEpoch;
            const actor = this.#state.user;
            if (actor === null) throw new APIError(401, 'Authentication is required.', { code: 'authentication_error' });
            let result: IdentityMutationSuccess;
            try {
                result = await this.#recovery.runInitiated(actor.id, await resolveStorage(), request, this.#recoveryAbortController.signal);
            } catch (error) {
                const runtimeError = ensureError(error);
                if (runtimeError instanceof APIError && runtimeError.status === 401) {
                    beginTerminalAuthIntent(this.#state);
                    await invalidateSessionAuthManager(this.#state, resolveStorage);
                }
                throw runtimeError;
            }
            await this.#reconcileAuthenticatedUser(result.user, epoch, resolveStorage);
            return result;
        });
    }

    async recoverRotatedSession(): Promise<void> {
        const [resolveApi, resolveStorage] = this.#createAuthResolvers();
        await this.#transitions.runCookieMutation(async (): Promise<void> => {
            const epoch = this.#state.authEpoch;
            try {
                const api = await resolveApi();
                const user = await this.#recovery.recoverClosure(api, this.#recoveryAbortController.signal);
                await this.#reconcileAuthenticatedUser(user, epoch, resolveStorage);
                const operation = await this.#recovery.resume(user, api, await resolveStorage(), this.#recoveryAbortController.signal);
                if (operation !== null) await this.#reconcileAuthenticatedUser(operation.user, epoch, resolveStorage);
            } catch (error) {
                const runtimeError = ensureError(error);
                if (runtimeError instanceof APIError && runtimeError.status === 401) {
                    beginTerminalAuthIntent(this.#state);
                    await invalidateSessionAuthManager(this.#state, resolveStorage);
                }
                throw runtimeError;
            }
        });
    }

    async checkWizardStatus(): Promise<boolean> {
        const [resolveApi] = this.#createAuthResolvers();
        return checkWizardStatus(this.#state, resolveApi);
    }

    getWizardStatusSnapshot(): WizardStatus | null {
        return getWizardStatusSnapshot(this.#state);
    }

    onLogin(callback: LoginCallback): () => void {
        return onAuthLogin(this.#state, callback);
    }

    onLogout(callback: AuthCallback): () => void {
        return onAuthLogout(this.#state, callback);
    }

    async notifyLogin(): Promise<void> {
        await notifyLogin(this.#state);
    }

    async notifyLogout(): Promise<void> {
        await notifyLogout(this.#state);
    }

    getCurrentUser(): WebuiUser | null {
        return this.#state.user;
    }

    isAdmin(): boolean {
        return Boolean(this.user?.isAdmin);
    }

    async #runTerminalTransition(operation: () => Promise<SessionInvalidationResult>): Promise<SessionInvalidationResult> {
        if (this.#terminalTask !== null) {
            return await this.#terminalTask;
        }
        beginTerminalAuthIntent(this.#state);
        this.#recoveryAbortController.abort();
        this.#recoveryAbortController = new AbortController();
        this.#recovery.reset();
        const task = this.#transitions.runCookieMutation(operation);
        this.#terminalTask = task;
        try {
            return await task;
        } finally {
            if (this.#terminalTask === task) {
                this.#terminalTask = null;
            }
        }
    }

    async #reconcileAuthenticatedUser(user: WebuiUser, epoch: number, resolveStorage: () => Promise<StorageInterface>): Promise<void> {
        const current = this.#state.user;
        if (!current || current.id !== user.id || this.#state.terminalEpoch !== null || this.#state.authEpoch !== epoch) {
            return;
        }
        const decision = compareWebuiUserRevision(current, user);
        if (decision === 'integrity_error') {
            throw new Error('Authenticated user revision contains conflicting identity fields.');
        }
        if (decision === 'stale') {
            return;
        }
        await applyUserSession(this.#state, user, resolveStorage, undefined, epoch);
    }

    reset(): void {
        resetAuthManagerState(this.#state);
        this.#api = null;
        this.#storage = null;
        this.#resolverApi = null;
        this.#resolverStorage = null;
        this.#terminalTask = null;
        this.#recoveryAbortController.abort();
        this.#recoveryAbortController = new AbortController();
        this.#recovery.reset();
        this.#transitions.reset();
    }
}

const getAuthManager = (): AuthManager => {
    const candidate = resolveKernelService('core.auth');
    if (!(candidate instanceof AuthManager)) {
        throw new Error('core.auth is not registered');
    }
    return candidate;
};

const resetAuthManager = (): void => {
    getAuthManager().reset();
};

export { AuthManager, getAuthManager, resetAuthManager };
export type { AuthCallback, LoginCallback };
