/* SoAI - Shared auth internal contracts [frontend/assets/ts/core/auth/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiInterface, AuthCallback, LoginCallback, SessionInvalidationResult, StateManager, StorageInterface, WebuiUser, WizardStatus } from '@core/auth/types.ts';
import type { CrossTabRevision } from '@core/crosstab/revision.ts';

interface AuthManagerStateHandle {
    user: WebuiUser | null;
    isAuthenticated: boolean;
    loginCallbacks: LoginCallback[];
    logoutCallbacks: AuthCallback[];
    stateKey: string;
    stateManager: StateManager | null;
    stateSubscription: (() => void) | null;
    stateRevision: CrossTabRevision | null;
    stateConnectPromise: Promise<StateManager | null> | null;
    sharedStateCommitTask: Promise<void> | null;
    sharedStateGeneration: number;
    isApplyingSharedState: boolean;
    isLoggingOut: boolean;
    sessionInvalidationPromise: Promise<SessionInvalidationResult> | null;
    wizardStatusSnapshot: WizardStatus | null;
    authEpoch: number;
    terminalEpoch: number | null;
}

interface AuthManagerServiceResolver {
    resolveApi(): Promise<ApiInterface>;
    resolveStorage(): Promise<StorageInterface>;
}

export type { AuthManagerServiceResolver, AuthManagerStateHandle };
