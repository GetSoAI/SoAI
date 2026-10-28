/* SoAI - Epoch-owned read-only session reconciliation [frontend/assets/ts/core/auth/sessionReconciliation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { AUTH_TAG } from '@core/auth/constants.ts';
import { invalidateSessionAuthManager } from '@core/auth/effects.ts';
import type { AuthManagerStateHandle, AuthManagerServiceResolver } from '@core/auth/internalContracts.ts';
import { applyUserSession, beginAuthenticatedEpoch, beginTerminalAuthIntent } from '@core/auth/state.ts';
import type { AuthTransitionOwner } from '@core/auth/transitionOwner.ts';
import type { SessionReconciliationResult, WebuiUser } from '@core/auth/types.ts';
import { createAbortSignalScope, raceWithAbortSignal } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { compareWebuiUserRevision } from '@core/users/userRevision.ts';

interface SessionReconciliationRequest extends AuthManagerServiceResolver {
    state: AuthManagerStateHandle;
    transitions: AuthTransitionOwner;
    signal: AbortSignal;
    authSignal: AbortSignal;
}

const requiresIdentityReconciliation = (current: WebuiUser | null, incoming: WebuiUser): boolean => {
    if (current === null || current.id !== incoming.id) return true;
    const decision = compareWebuiUserRevision(current, incoming);
    if (decision === 'integrity_error') throw new Error('Authenticated user revision contains conflicting identity fields.');
    return decision === 'newer' || (decision === 'equal' && current.workspacePathResolved !== incoming.workspacePathResolved);
};

const reconcileAuthSession = async (request: SessionReconciliationRequest): Promise<SessionReconciliationResult> => {
    const scope = createAbortSignalScope([request.signal, request.authSignal]);
    let result: SessionReconciliationResult;
    try {
        result = await raceWithAbortSignal(readAuthSession({ ...request, signal: scope.signal }), scope.signal);
    } catch (error) {
        if (request.signal.aborted || !request.authSignal.aborted) throw error;
        result = { status: 'superseded', authEpoch: request.state.authEpoch };
    } finally {
        scope.cleanup();
    }
    if (result.status !== 'superseded' && result.authEpoch === request.state.authEpoch) return result;
    await raceWithAbortSignal(request.transitions.waitForCookieTransition(), request.signal);
    return { status: request.state.isAuthenticated ? 'superseded' : 'invalidated', authEpoch: request.state.authEpoch };
};

const readAuthSession = async (request: SessionReconciliationRequest): Promise<SessionReconciliationResult> => {
    const expectedEpoch = request.state.authEpoch;
    const isCurrent = (): boolean => !request.signal.aborted && request.state.authEpoch === expectedEpoch && request.state.terminalEpoch === null;
    await raceWithAbortSignal(request.transitions.waitForCookieTransition(), request.signal);
    if (!isCurrent()) return { status: 'superseded', authEpoch: request.state.authEpoch };
    const api = await request.resolveApi();
    if (!isCurrent()) return { status: 'superseded', authEpoch: request.state.authEpoch };
    let recheckCurrentCookie = false;
    try {
        const user = await api.webui.auth.getMe({ signal: request.signal, authTransitionOwned: true });
        if (!isCurrent()) return { status: 'superseded', authEpoch: request.state.authEpoch };
        recheckCurrentCookie = requiresIdentityReconciliation(request.state.user, user);
    } catch (error) {
        if (!isCurrent()) return { status: 'superseded', authEpoch: request.state.authEpoch };
        const runtimeError = ensureError(error);
        if (!(runtimeError instanceof APIError && (runtimeError.status === 401 || runtimeError.status === 403))) throw runtimeError;
        recheckCurrentCookie = true;
    }
    if (!recheckCurrentCookie) return { status: 'confirmed', authEpoch: request.state.authEpoch };
    return await request.transitions.runCookieMutation(async (): Promise<SessionReconciliationResult> => {
        if (!isCurrent()) return { status: 'superseded', authEpoch: request.state.authEpoch };
        let user: WebuiUser;
        try {
            user = await raceWithAbortSignal(api.webui.auth.getMe({ signal: request.signal, authTransitionOwned: true }), request.signal);
        } catch (error) {
            if (!isCurrent()) return { status: 'superseded', authEpoch: request.state.authEpoch };
            const runtimeError = ensureError(error);
            if (!(runtimeError instanceof APIError && runtimeError.status === 401)) throw runtimeError;
            errorHandler.debug(AUTH_TAG, 'Authenticated session recheck rejected the current cookie.');
            beginTerminalAuthIntent(request.state);
            await invalidateSessionAuthManager(request.state, request.resolveStorage);
            return { status: 'invalidated', authEpoch: request.state.authEpoch };
        }
        if (!isCurrent()) return { status: 'superseded', authEpoch: request.state.authEpoch };
        if (!requiresIdentityReconciliation(request.state.user, user)) return { status: 'confirmed', authEpoch: request.state.authEpoch };
        const epoch = beginAuthenticatedEpoch(request.state);
        await applyUserSession(request.state, user, request.resolveStorage, undefined, epoch);
        return { status: 'superseded', authEpoch: request.state.authEpoch };
    });
};

export { reconcileAuthSession };
