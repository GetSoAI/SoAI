/* SoAI - Shared authentication contracts [frontend/assets/ts/core/auth/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessageResponse, WebuiUser, WizardCompleteResponse, WizardStatusLookupResponse, WizardStatusResponse } from '@core/api/contracts/webuiUserContracts.ts';
import type { IdentityMutationStatus, IdentityMutationSuccess, SessionRotationRecovery } from '@core/api/contracts/webuiIdentityMutationContracts.ts';
import type { WizardCompletedSummary } from '@core/api/contracts/wizardLicensingContracts.ts';
import type { CrossTabRevision } from '@core/crosstab/revision.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { CrossTabPublishOutcome } from '@core/crosstab/channel.ts';
import type { IdentityMutationType } from '@core/users/identityMutationContract.ts';

interface SessionPayload {
    userId: string;
    username: string;
    isAdmin: boolean;
    loginTime: string;
}

type WizardStatus = WizardStatusResponse;

interface SharedAuthState {
    revision: CrossTabRevision;
    isAuthenticated: boolean;
    user: WebuiUser | null;
}

interface TabStateEvent {
    key: string;
    remote?: boolean;
    value: JsonValue | null;
}

interface StateManager {
    subscribeTabState(callback: (event: TabStateEvent) => void): () => void;
    setTabState(key: string, value: JsonValue | null): void;
    getTabState(key: string): JsonValue | null;
    getCrossTabChannel: (channelId: string) => {
        publish: (message: JsonValue | null) => CrossTabPublishOutcome;
        subscribe: (listener: (message: JsonValue | null) => void) => () => void;
        close: () => void;
    };
}

interface StorageInterface {
    get(key: string, defaultValue?: JsonValue | null): JsonValue | null;
    set(key: string, value: JsonValue | null): void;
    remove(key: string): void;
    flushPending(): Promise<void>;
    setAuthenticated(value: boolean, options?: { authTransitionOwned?: boolean }): void | Promise<void>;
    setSession(session: SessionPayload): void;
    clearSession(): void;
    clearRedirectAfterLogin(): void;
    isWizardCompletionPending(): boolean;
    setWizardCompletionPending(value: boolean): void;
}

interface AuthApiInterface {
    getMe(options?: { signal?: AbortSignal; authTransitionOwned?: boolean }): Promise<WebuiUser>;
    login(username: string, password: string): Promise<MessageResponse>;
    logout(): Promise<MessageResponse>;
    changePassword(operationId: string, current: string, newPassword: string, options?: { signal?: AbortSignal }): Promise<IdentityMutationSuccess>;
    recoverSessionRotation(operationId: string | null, options?: { signal?: AbortSignal; authTransitionOwned?: boolean }): Promise<SessionRotationRecovery>;
}

interface WizardApiInterface {
    status(options?: { signal?: AbortSignal; authTransitionOwned?: boolean }): Promise<WizardStatusLookupResponse>;
    complete(draftRevision: number, username: string, password: string, language: string, options?: { signal?: AbortSignal; authTransitionOwned?: boolean }): Promise<WizardCompleteResponse>;
}

interface ApiInterface {
    webui: {
        auth: AuthApiInterface;
        wizard: WizardApiInterface;
        users: {
            current(options?: { signal?: AbortSignal; authTransitionOwned?: boolean }): Promise<WebuiUser>;
            mutationStatus(operationId: string, finalization?: { operationType: IdentityMutationType; targetUserId: number; requestedUsername?: string }, options?: { signal?: AbortSignal; authTransitionOwned?: boolean }): Promise<IdentityMutationStatus>;
        };
    };
}

interface RouterInterface {
    navigate(route: string, options?: { force?: boolean }): void;
}

interface LayoutShellInterface {
    teardown(): Promise<void>;
}

interface InitializeOptions {
    wizardState?: WizardStatus | null;
    skipSessionProbe?: boolean;
}

type LoginResult = { status: 'authenticated'; user: WebuiUser } | { status: 'rejected'; error: string; retryAfterSeconds?: number } | { status: 'sessionActivationFailed'; error: string };

type WizardCompletionResult = { status: 'authenticated'; user: WebuiUser; completion: WizardCompletedSummary } | { status: 'sessionActivationFailed'; user: WebuiUser | null; completion: WizardCompletedSummary; error: string } | { status: 'reconciliationPending'; error: string } | { status: 'rejected'; error: string };

interface SessionInvalidationResult {
    status: 'signedOut';
}

type AuthCallback = () => void | Promise<void>;
type LoginCallback = (user: WebuiUser | null) => void | Promise<void>;

export type { AuthCallback, InitializeOptions, LayoutShellInterface, LoginCallback, LoginResult, RouterInterface, SessionInvalidationResult, SessionPayload, SharedAuthState, StateManager, StorageInterface, ApiInterface, AuthApiInterface, TabStateEvent, WebuiUser, WizardApiInterface, WizardCompletionResult, WizardStatus };
