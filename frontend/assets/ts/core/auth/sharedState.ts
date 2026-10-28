/* SoAI - Cross-tab authentication state synchronization [frontend/assets/ts/core/auth/sharedState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { requireStateManager } from '@core/state/runtime.ts';
import { createModuleLogger } from '@core/moduleContext.ts';
import { compareCrossTabRevision, createNextCrossTabRevision, serializeCrossTabRevision } from '@core/crosstab/revision.ts';
import { hasStateInterface } from '@core/auth/adapters.ts';
import { AUTH_TAG } from '@core/auth/constants.ts';
import type { SharedAuthState, StateManager, StorageInterface, WebuiUser } from '@core/auth/types.ts';
import type { AuthManagerStateHandle } from '@core/auth/internalContracts.ts';
import { parseSharedAuthState, serializeSharedAuthState, serializeUser } from '@core/auth/stateMappers.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import { compareWebuiUserRevision } from '@core/users/userRevision.ts';

const log = createModuleLogger(AUTH_TAG, { defaultLevel: 'warn' });

const AUTH_CROSS_TAB_CHANNEL_ID = 'soai.webui.auth';
const AUTH_CROSS_TAB_MESSAGE_TYPE = 'auth.status';

interface SharedStateHooks {
    notifyLogin: (state: AuthManagerStateHandle) => Promise<void>;
    notifyLogout: (state: AuthManagerStateHandle) => Promise<void>;
    persistLogin: (user: WebuiUser) => Promise<void>;
    persistLogout: () => Promise<void>;
    probeAuthenticatedUser: (announcement: WebuiUser) => Promise<WebuiUser | null>;
}

type UserSerializer = (value: WebuiUser) => Promise<WebuiUser>;
type SharedStateTransitionRunner = <T>(operation: () => Promise<T>) => Promise<T>;

interface SharedStateOwnership {
    revision: SharedAuthState['revision'];
    generation: number;
    authEpoch: number;
}

const runDirectSharedStateTransition: SharedStateTransitionRunner = async (operation) => await operation();

const resolveStorageStateManager = (): StateManager => {
    const stateManager = requireStateManager();
    if (!hasStateInterface(stateManager)) {
        throw new Error('State manager must expose tab state accessors');
    }
    return stateManager;
};

const isCurrentSharedRevision = (state: AuthManagerStateHandle, ownership: SharedStateOwnership): boolean => {
    return state.sharedStateGeneration === ownership.generation && state.authEpoch === ownership.authEpoch && compareCrossTabRevision(ownership.revision, state.stateRevision) === 0;
};

const acceptsSharedUserRevision = (state: AuthManagerStateHandle, user: WebuiUser): boolean => {
    if (!state.isAuthenticated || !state.user || state.user.id !== user.id || state.terminalEpoch !== null) return true;
    const decision = compareWebuiUserRevision(state.user, user);
    if (decision === 'integrity_error') throw new Error('Shared user revision contains conflicting identity fields.');
    return decision !== 'stale';
};

const commitSharedState = async (state: AuthManagerStateHandle, snapshot: SharedAuthState, serialized: WebuiUser | null, hooks: SharedStateHooks, ownership: SharedStateOwnership): Promise<boolean> => {
    if (!isCurrentSharedRevision(state, ownership)) {
        return false;
    }
    const committedOwnership = { ...ownership, authEpoch: state.authEpoch + 1 };
    if (!snapshot.isAuthenticated) {
        state.authEpoch = committedOwnership.authEpoch;
        state.terminalEpoch = state.authEpoch;
    }
    state.isApplyingSharedState = true;
    try {
        if (snapshot.isAuthenticated && serialized) {
            if (!acceptsSharedUserRevision(state, serialized)) return false;
            let candidate = serialized;
            const previousUser = state.user && isObject(state.user) ? state.user : null;
            if (!previousUser || !state.isAuthenticated || previousUser.id !== serialized.id || state.terminalEpoch !== null) {
                const probedTerminalEpoch = state.terminalEpoch;
                const verified = await hooks.probeAuthenticatedUser(serialized);
                if (verified === null || verified.id !== serialized.id || !isCurrentSharedRevision(state, ownership) || state.terminalEpoch !== probedTerminalEpoch) return false;
                candidate = verified;
            }
            const wasAuthenticated = state.isAuthenticated;
            const userChanged = !previousUser || previousUser.id !== candidate.id || previousUser.identityRevision !== candidate.identityRevision || previousUser.workspacePathResolved !== candidate.workspacePathResolved;
            await hooks.persistLogin(candidate);
            if (!isCurrentSharedRevision(state, ownership) || state.isLoggingOut) {
                return false;
            }
            state.authEpoch = committedOwnership.authEpoch;
            state.terminalEpoch = null;
            state.user = candidate;
            state.isAuthenticated = true;
            if (!wasAuthenticated || userChanged) {
                await hooks.notifyLogin(state);
            }
            return isCurrentSharedRevision(state, committedOwnership);
        }
        if (!snapshot.isAuthenticated && state.isAuthenticated) {
            await hooks.persistLogout();
            if (!isCurrentSharedRevision(state, committedOwnership)) {
                return false;
            }
            state.user = null;
            state.isAuthenticated = false;
            await hooks.notifyLogout(state);
            return isCurrentSharedRevision(state, committedOwnership);
        }
        return false;
    } finally {
        state.isApplyingSharedState = false;
    }
};

const queueSharedStateCommit = async (state: AuthManagerStateHandle, snapshot: SharedAuthState, serialized: WebuiUser | null, hooks: SharedStateHooks, ownership: SharedStateOwnership, runTransition: SharedStateTransitionRunner): Promise<boolean> => {
    const previousCommit = state.sharedStateCommitTask;
    const execute = async (): Promise<boolean> => {
        if (previousCommit) {
            await previousCommit;
        }
        return await runTransition(async () => await commitSharedState(state, snapshot, serialized, hooks, ownership));
    };
    const commitTask = execute();
    const queueTail = commitTask.then(
        (): void => undefined,
        (): void => undefined
    );
    state.sharedStateCommitTask = queueTail;
    try {
        return await commitTask;
    } catch (error) {
        throw ensureError(error);
    } finally {
        if (state.sharedStateCommitTask === queueTail) {
            state.sharedStateCommitTask = null;
        }
    }
};

const applySharedState = async (state: AuthManagerStateHandle, snapshot: SharedAuthState | null, hooks: SharedStateHooks, serialize: UserSerializer = serializeUser, initial = false, runTransition: SharedStateTransitionRunner = runDirectSharedStateTransition): Promise<boolean> => {
    if (!snapshot || !isObject(snapshot)) {
        return false;
    }
    const revision = snapshot.revision;
    if (!initial && compareCrossTabRevision(revision, state.stateRevision) <= 0) {
        return false;
    }
    const isAuthenticated = Boolean(snapshot.isAuthenticated);
    if (initial && isAuthenticated) {
        state.stateRevision = revision;
        return false;
    }
    const user = snapshot.user;
    const hasUser = isAuthenticated && user !== null && isObject(user);
    if (isAuthenticated && !hasUser) return false;
    if (hasUser && !acceptsSharedUserRevision(state, user)) return false;
    state.stateRevision = revision;
    const ownership = { revision, generation: state.sharedStateGeneration, authEpoch: state.authEpoch };
    const serialized = hasUser ? await serialize(user) : null;
    return await queueSharedStateCommit(state, snapshot, serialized, hooks, ownership, runTransition);
};

const connectSharedState = async (state: AuthManagerStateHandle, hooks: SharedStateHooks, serialize: UserSerializer = serializeUser, runTransition: SharedStateTransitionRunner = runDirectSharedStateTransition): Promise<StateManager | null> => {
    if (state.stateManager && state.stateSubscription) return state.stateManager;
    if (state.stateConnectPromise) {
        return await state.stateConnectPromise;
    }
    const generation = state.sharedStateGeneration;
    const connectTask = (async (): Promise<StateManager | null> => {
        const manager = resolveStorageStateManager();
        if (isFunction(manager.getTabState)) {
            const snapshot = manager.getTabState(state.stateKey);
            if (snapshot) {
                try {
                    await applySharedState(state, parseSharedAuthState(snapshot), hooks, serialize, true);
                } catch (error) {
                    const err = ensureError(error);
                    log('warn', 'Initial state application failed (non-blocking)', err);
                }
            }
        }
        if (state.sharedStateGeneration !== generation) {
            return null;
        }
        if (!state.stateSubscription) {
            if (!isFunction(manager.getCrossTabChannel)) {
                throw new Error('AuthManager requires stateManager.getCrossTabChannel for cross-tab sync');
            }
            const channel = manager.getCrossTabChannel(AUTH_CROSS_TAB_CHANNEL_ID);
            state.stateSubscription = channel.subscribe((message) => {
                if (!isObject(message)) {
                    return;
                }
                if (message['type'] !== AUTH_CROSS_TAB_MESSAGE_TYPE) {
                    return;
                }
                try {
                    const origin = message['origin'];
                    if (isString(origin) && origin.trim() && origin.trim() === windowIdentity.current()) {
                        return;
                    }
                } catch (error) {
                    const err = ensureError(error);
                    log('debug', 'Failed to read cross-tab auth message origin', err);
                }
                const payload = message['payload'];
                const normalized = parseSharedAuthState(payload);
                if (!normalized) {
                    return;
                }
                void applySharedState(state, normalized, hooks, serialize, false, runTransition)
                    .then((applied) => {
                        if (!applied) {
                            return;
                        }
                        try {
                            manager.setTabState(state.stateKey, serializeSharedAuthState(normalized));
                        } catch (error) {
                            const err = ensureError(error);
                            log('warn', 'Failed to persist cross-tab auth state snapshot', err);
                        }
                    })
                    .catch((error) => {
                        const err = ensureError(error);
                        log('warn', 'Cross-tab auth state application failed (non-blocking)', err);
                    });
            });
        }
        state.stateManager = manager;
        return manager;
    })();
    state.stateConnectPromise = connectTask;
    try {
        return await connectTask;
    } finally {
        if (state.stateConnectPromise === connectTask) {
            state.stateConnectPromise = null;
        }
    }
};

const canPublishAuthenticatedEpoch = (state: AuthManagerStateHandle, expectedAuthEpoch: number | null): boolean => expectedAuthEpoch === null || (state.authEpoch === expectedAuthEpoch && state.terminalEpoch === null);

const publishSharedState = async (state: AuthManagerStateHandle, hooks: SharedStateHooks, serialize: UserSerializer = serializeUser, expectedAuthEpoch: number | null = null): Promise<void> => {
    if (state.isApplyingSharedState) return;
    const generation = state.sharedStateGeneration;
    const manager = (await connectSharedState(state, hooks, serialize)) ?? state.stateManager;
    if (state.sharedStateGeneration !== generation || !canPublishAuthenticatedEpoch(state, expectedAuthEpoch) || !manager || !isFunction(manager.setTabState)) return;
    const origin = await windowIdentity.get();
    if (state.sharedStateGeneration !== generation || !canPublishAuthenticatedEpoch(state, expectedAuthEpoch)) return;
    const isAuthenticated = state.isAuthenticated;
    const user = state.user;
    const serializedUser = isAuthenticated && user ? await serialize(user) : null;
    if (state.sharedStateGeneration !== generation || !canPublishAuthenticatedEpoch(state, expectedAuthEpoch) || state.isAuthenticated !== isAuthenticated || state.user !== user) return;
    const payload: SharedAuthState = {
        revision: createNextCrossTabRevision(state.stateRevision, origin),
        isAuthenticated,
        user: serializedUser
    };
    state.stateRevision = payload.revision;
    const serializedPayload = serializeSharedAuthState(payload);
    manager.setTabState(state.stateKey, serializedPayload);
    if (!isFunction(manager.getCrossTabChannel)) {
        return;
    }
    manager.getCrossTabChannel(AUTH_CROSS_TAB_CHANNEL_ID).publish({
        type: AUTH_CROSS_TAB_MESSAGE_TYPE,
        origin,
        revision: serializeCrossTabRevision(payload.revision),
        payload: serializedPayload
    });
};

const resetAuthSharedState = (state: AuthManagerStateHandle): void => {
    if (typeof state.stateSubscription === 'function') {
        try {
            state.stateSubscription();
        } catch (error) {
            const err = ensureError(error);
            log('debug', 'Auth state subscription dispose failed', err);
        }
    }
    state.stateManager = null;
    state.stateSubscription = null;
    state.stateRevision = null;
    state.stateConnectPromise = null;
    state.sharedStateGeneration += 1;
    state.isApplyingSharedState = false;
};

const safeSetStorageAuthenticated = async (resolveStorage: () => Promise<StorageInterface>, value: boolean): Promise<void> => {
    let storage: StorageInterface | null = null;
    try {
        storage = await resolveStorage();
        await storage.setAuthenticated(value, { authTransitionOwned: true });
    } catch (error) {
        const err = ensureError(error);
        if (value && storage?.isWizardCompletionPending() === true) {
            throw err;
        }
        errorHandler.warn(AUTH_TAG, 'Persisting authentication flag failed', err);
    }
};

export type { SharedStateHooks };
export { applySharedState, connectSharedState, publishSharedState, resetAuthSharedState, safeSetStorageAuthenticated };
