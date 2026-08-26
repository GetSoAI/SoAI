/* SoAI - Protected read authentication reconciliation gate [frontend/assets/ts/core/auth/protectedReadGate.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { AuthRecoverySupervisor } from '@core/auth/recoverySupervisor.ts';
import { invalidateSessionAuthManager } from '@core/auth/effects.ts';
import type { AuthManagerStateHandle } from '@core/auth/internalContracts.ts';
import { beginTerminalAuthIntent } from '@core/auth/state.ts';
import { AuthTransitionOwner } from '@core/auth/transitionOwner.ts';
import type { ApiInterface, StorageInterface, WebuiUser } from '@core/auth/types.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface ProtectedReadGateRequest {
    state: AuthManagerStateHandle;
    transitions: AuthTransitionOwner;
    recovery: AuthRecoverySupervisor;
    resolveApi: () => Promise<ApiInterface>;
    resolveStorage: () => Promise<StorageInterface>;
    signal: AbortSignal;
    reconcile: (user: WebuiUser) => Promise<void>;
}

const runProtectedReadGate = async (request: ProtectedReadGateRequest): Promise<void> => {
    await request.transitions.runCookieMutation(async (): Promise<void> => {
        try {
            const user = await request.recovery.probeStale(await request.resolveApi(), request.signal);
            if (user !== null) await request.reconcile(user);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (runtimeError instanceof APIError && runtimeError.status === 401) {
                beginTerminalAuthIntent(request.state);
                await invalidateSessionAuthManager(request.state, request.resolveStorage);
            }
            throw runtimeError;
        }
    });
};

export { runProtectedReadGate };
