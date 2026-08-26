/* SoAI - Auth-owned unresolved identity mutation recovery [frontend/assets/ts/core/auth/identityMutationRecovery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IdentityMutationStatus, IdentityMutationSuccess, SessionRotationRecovery } from '@core/api/contracts/webuiIdentityMutationContracts.ts';
import { APIError, isNetworkError } from '@core/apiError.ts';
import { runSelfMutationWithRecovery, type SelfMutationRecoveryRequest } from '@core/auth/rotationRecovery.ts';
import type { ApiInterface, StorageInterface, WebuiUser } from '@core/auth/types.ts';
import { clearUnresolvedIdentityMutation, readUnresolvedIdentityMutation, writeUnresolvedIdentityMutation, type UnresolvedIdentityMutation } from '@core/auth/unresolvedIdentityMutation.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { wallClockMs } from '@core/time/clock.ts';
import { IDENTITY_MUTATION_CLIENT_RECOVERY_MS, IDENTITY_MUTATION_FINAL_PROBE_MS, type IdentityMutationType } from '@core/users/identityMutationContract.ts';

interface InitiatedIdentityMutationRequest {
    operationId: string;
    operationType: IdentityMutationType;
    targetUserId: number;
    requestedUsername: string | null;
    execute: (signal: AbortSignal) => Promise<IdentityMutationSuccess>;
    recover: (signal: AbortSignal) => Promise<SessionRotationRecovery>;
    status: (finalizeAbsence: boolean, signal: AbortSignal) => Promise<IdentityMutationStatus>;
    currentUser: (signal: AbortSignal) => Promise<WebuiUser>;
}

const failureFromStatus = (status: Extract<IdentityMutationStatus, { status: 'failed' }>): APIError => new APIError(409, 'Identity mutation failed.', status.traceId === null ? { code: status.errorCode } : { code: status.errorCode, traceId: status.traceId });

const createRecord = (actorId: number, request: InitiatedIdentityMutationRequest): UnresolvedIdentityMutation => {
    if (request.targetUserId !== actorId) throw new Error('Self identity mutation target must match the authenticated actor.');
    if ((request.operationType === 'username_rename') !== (request.requestedUsername !== null)) throw new Error('Identity mutation requested username does not match its operation type.');
    const recoveryDeadlineMs = wallClockMs() + IDENTITY_MUTATION_CLIENT_RECOVERY_MS;
    return { actorId, operationId: request.operationId, operationType: request.operationType, targetUserId: request.targetUserId, requestedUsername: request.requestedUsername, recoveryDeadlineMs, finalProbeDeadlineMs: recoveryDeadlineMs + IDENTITY_MUTATION_FINAL_PROBE_MS, stale: false };
};

const buildRecoveryRequest = (request: InitiatedIdentityMutationRequest, record: UnresolvedIdentityMutation, signal: AbortSignal): SelfMutationRecoveryRequest => ({
    operationId: request.operationId,
    execute: request.execute,
    recover: request.recover,
    status: request.status,
    currentUser: request.currentUser,
    recoveryDeadlineMs: record.recoveryDeadlineMs,
    finalProbeDeadlineMs: record.finalProbeDeadlineMs,
    signal
});

const retainOrClearFailure = async (storage: StorageInterface, record: UnresolvedIdentityMutation, error: Error): Promise<void> => {
    if (error.name === 'AbortError') return;
    if (error instanceof APIError && error.code === 'identity_mutation_result_unknown') {
        await writeUnresolvedIdentityMutation(storage, { ...record, stale: true });
        return;
    }
    await clearUnresolvedIdentityMutation(storage);
};

const normalizeRecoveryFailure = (error: Error): Error => (isNetworkError(error) ? new APIError(503, 'Identity mutation result remains unknown.', { code: 'identity_mutation_result_unknown', cause: error }) : error);

const runInitiatedIdentityMutation = async (actorId: number, storage: StorageInterface, request: InitiatedIdentityMutationRequest, signal: AbortSignal): Promise<IdentityMutationSuccess> => {
    const record = createRecord(actorId, request);
    await writeUnresolvedIdentityMutation(storage, record);
    try {
        const result = await runSelfMutationWithRecovery(buildRecoveryRequest(request, record, signal));
        await clearUnresolvedIdentityMutation(storage);
        return result;
    } catch (error) {
        const runtimeError = normalizeRecoveryFailure(ensureError(error));
        await retainOrClearFailure(storage, record, runtimeError);
        throw runtimeError;
    }
};

const statusSuccess = async (api: ApiInterface, status: IdentityMutationStatus, signal: AbortSignal): Promise<IdentityMutationSuccess | null> => {
    if (status.status === 'not_found') return null;
    if (status.status === 'failed') throw failureFromStatus(status);
    return { operationId: status.operationId, user: await api.webui.users.current({ signal, authTransitionOwned: true }) };
};

const resumeUnresolvedIdentityMutation = async (actor: WebuiUser, api: ApiInterface, storage: StorageInterface, signal: AbortSignal): Promise<IdentityMutationSuccess | null> => {
    let record: UnresolvedIdentityMutation | null;
    try {
        record = readUnresolvedIdentityMutation(storage);
    } catch (error) {
        await clearUnresolvedIdentityMutation(storage);
        throw ensureError(error);
    }
    if (record === null || record.actorId !== actor.id) return null;
    try {
        if (record.stale || wallClockMs() >= record.finalProbeDeadlineMs) {
            const finalization = { operationType: record.operationType, targetUserId: record.targetUserId, ...(record.requestedUsername === null ? {} : { requestedUsername: record.requestedUsername }) };
            const result = await statusSuccess(api, await api.webui.users.mutationStatus(record.operationId, finalization, { signal, authTransitionOwned: true }), signal);
            if (result === null) throw new APIError(503, 'Identity mutation result remains unknown.', { code: 'identity_mutation_result_unknown' });
            await clearUnresolvedIdentityMutation(storage);
            return result;
        }
        const request: SelfMutationRecoveryRequest = {
            operationId: record.operationId,
            execute: null,
            recover: (recoverySignal) => api.webui.auth.recoverSessionRotation(record.operationId, { signal: recoverySignal, authTransitionOwned: true }),
            status: (finalizeAbsence, statusSignal) => api.webui.users.mutationStatus(record.operationId, finalizeAbsence ? { operationType: record.operationType, targetUserId: record.targetUserId, ...(record.requestedUsername === null ? {} : { requestedUsername: record.requestedUsername }) } : undefined, { signal: statusSignal, authTransitionOwned: true }),
            currentUser: (currentSignal) => api.webui.users.current({ signal: currentSignal, authTransitionOwned: true }),
            recoveryDeadlineMs: record.recoveryDeadlineMs,
            finalProbeDeadlineMs: record.finalProbeDeadlineMs,
            signal
        };
        const result = await runSelfMutationWithRecovery(request);
        await clearUnresolvedIdentityMutation(storage);
        return result;
    } catch (error) {
        const runtimeError = normalizeRecoveryFailure(ensureError(error));
        await retainOrClearFailure(storage, record, runtimeError);
        throw runtimeError;
    }
};

export { resumeUnresolvedIdentityMutation, runInitiatedIdentityMutation };
export type { InitiatedIdentityMutationRequest };
