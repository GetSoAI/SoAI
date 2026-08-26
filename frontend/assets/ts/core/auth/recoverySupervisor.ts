/* SoAI - Auth transition session and identity recovery supervisor [frontend/assets/ts/core/auth/recoverySupervisor.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IdentityMutationSuccess } from '@core/api/contracts/webuiIdentityMutationContracts.ts';
import { APIError } from '@core/apiError.ts';
import { resumeUnresolvedIdentityMutation, runInitiatedIdentityMutation, type InitiatedIdentityMutationRequest } from '@core/auth/identityMutationRecovery.ts';
import { recoverSessionFromClosure } from '@core/auth/rotationRecovery.ts';
import type { ApiInterface, StorageInterface, WebuiUser } from '@core/auth/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { wallClockMs } from '@core/time/clock.ts';
import { IDENTITY_MUTATION_CLIENT_RECOVERY_MS, IDENTITY_MUTATION_FINAL_PROBE_MS } from '@core/users/identityMutationContract.ts';

class AuthRecoverySupervisor {
    #stale = false;
    #closureRecoveryTask: Promise<WebuiUser> | null = null;

    get stale(): boolean {
        return this.#stale;
    }

    async runInitiated(actorId: number, storage: StorageInterface, request: InitiatedIdentityMutationRequest, signal: AbortSignal): Promise<IdentityMutationSuccess> {
        try {
            const result = await runInitiatedIdentityMutation(actorId, storage, request, signal);
            this.#stale = false;
            return result;
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#observeFailure(runtimeError);
            throw runtimeError;
        }
    }

    async resume(actor: WebuiUser, api: ApiInterface, storage: StorageInterface, signal: AbortSignal): Promise<IdentityMutationSuccess | null> {
        try {
            const result = await resumeUnresolvedIdentityMutation(actor, api, storage, signal);
            if (result !== null) this.#stale = false;
            return result;
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#observeFailure(runtimeError);
            throw runtimeError;
        }
    }

    async recoverClosure(api: ApiInterface, signal: AbortSignal): Promise<WebuiUser> {
        if (this.#closureRecoveryTask !== null) return await this.#closureRecoveryTask;
        const recoveryDeadlineMs = wallClockMs() + IDENTITY_MUTATION_CLIENT_RECOVERY_MS;
        const recoveryTask = recoverSessionFromClosure({
            recover: (recoverySignal) => api.webui.auth.recoverSessionRotation(null, { signal: recoverySignal, authTransitionOwned: true }),
            recoveryDeadlineMs,
            finalProbeDeadlineMs: recoveryDeadlineMs + IDENTITY_MUTATION_FINAL_PROBE_MS,
            signal
        });
        this.#closureRecoveryTask = recoveryTask;
        try {
            const user = await recoveryTask;
            this.#stale = false;
            if (this.#closureRecoveryTask === recoveryTask) this.#closureRecoveryTask = null;
            return user;
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#observeFailure(runtimeError);
            if (!(runtimeError instanceof APIError && runtimeError.code === 'identity_mutation_result_unknown') && this.#closureRecoveryTask === recoveryTask) this.#closureRecoveryTask = null;
            throw runtimeError;
        }
    }

    async probeStale(api: ApiInterface, signal: AbortSignal): Promise<WebuiUser | null> {
        if (!this.#stale) return null;
        const user = await api.webui.auth.getMe({ signal, authTransitionOwned: true });
        this.#stale = false;
        return user;
    }

    reset(): void {
        this.#stale = false;
        this.#closureRecoveryTask = null;
    }

    #observeFailure(error: Error): void {
        if (error instanceof APIError && error.code === 'identity_mutation_result_unknown') this.#stale = true;
    }
}

export { AuthRecoverySupervisor };
