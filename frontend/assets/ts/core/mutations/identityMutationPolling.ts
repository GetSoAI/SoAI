/* SoAI - Non-rotating identity mutation status recovery [frontend/assets/ts/core/mutations/identityMutationPolling.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IdentityMutationStatus, IdentityMutationSuccess } from '@core/api/contracts/webuiIdentityMutationContracts.ts';
import { APIError, isNetworkError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { requirePerformanceNow } from '@core/environment/public.ts';
import { IDENTITY_MUTATION_DEADLINE_MS, IDENTITY_MUTATION_FINAL_PROBE_MS, IDENTITY_MUTATION_NETWORK_ALLOWANCE_MS } from '@core/users/identityMutationContract.ts';

interface IdentityMutationPollingRequest {
    operationId: string;
    execute: (signal: AbortSignal) => Promise<IdentityMutationSuccess>;
    status: (finalizeAbsence: boolean, signal: AbortSignal) => Promise<IdentityMutationStatus>;
    resolveCommittedUser: (signal: AbortSignal) => Promise<IdentityMutationSuccess['user']>;
    signal: AbortSignal;
}

const statusFailure = (status: Extract<IdentityMutationStatus, { status: 'failed' }>): APIError => new APIError(409, 'Identity mutation failed.', status.traceId === null ? { code: status.errorCode } : { code: status.errorCode, traceId: status.traceId });

const classifyStatus = async (request: IdentityMutationPollingRequest, status: IdentityMutationStatus): Promise<IdentityMutationSuccess | null> => {
    if (status.status === 'not_found') return null;
    if (status.operationId !== request.operationId) throw new APIError(409, 'Identity operation binding changed.', { code: 'operation_id_conflict' });
    if (status.status === 'failed') throw statusFailure(status);
    return { operationId: status.operationId, user: await request.resolveCommittedUser(request.signal) };
};

const sleep = async (milliseconds: number, signal: AbortSignal): Promise<void> => {
    if (signal.aborted) throw new DOMException('Identity mutation polling was cancelled.', 'AbortError');
    await new Promise<void>((resolve, reject) => {
        const finish = (): void => {
            signal.removeEventListener('abort', abort);
            resolve();
        };
        const abort = (): void => {
            globalThis.clearTimeout(timer);
            signal.removeEventListener('abort', abort);
            reject(new DOMException('Identity mutation polling was cancelled.', 'AbortError'));
        };
        const timer = globalThis.setTimeout(finish, milliseconds);
        signal.addEventListener('abort', abort, { once: true });
    });
};

const pollOnce = async (request: IdentityMutationPollingRequest, finalizeAbsence: boolean): Promise<IdentityMutationSuccess | null> => {
    try {
        return await classifyStatus(request, await request.status(finalizeAbsence, request.signal));
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!finalizeAbsence && runtimeError instanceof APIError && runtimeError.code === 'user_mutation_not_found') return null;
        throw runtimeError;
    }
};

const runIdentityMutationWithStatusRecovery = async (request: IdentityMutationPollingRequest): Promise<IdentityMutationSuccess> => {
    const now = requirePerformanceNow();
    const deadline = now() + IDENTITY_MUTATION_DEADLINE_MS + IDENTITY_MUTATION_NETWORK_ALLOWANCE_MS;
    try {
        return await request.execute(request.signal);
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!isNetworkError(runtimeError) && (!(runtimeError instanceof APIError) || runtimeError.code !== 'identity_mutation_result_unknown')) throw runtimeError;
    }
    let backoffMs = 250;
    while (now() < deadline) {
        try {
            const result = await pollOnce(request, false);
            if (result !== null) return result;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isNetworkError(runtimeError)) throw runtimeError;
        }
        const remainingMs = deadline - now();
        if (remainingMs <= 0) break;
        await sleep(Math.min(backoffMs, remainingMs), request.signal);
        backoffMs = Math.min(backoffMs * 2, 2_000);
    }
    const finalController = new AbortController();
    const timeout = globalThis.setTimeout(() => finalController.abort(), IDENTITY_MUTATION_FINAL_PROBE_MS);
    const abortFinal = (): void => finalController.abort();
    request.signal.addEventListener('abort', abortFinal, { once: true });
    try {
        const result = await pollOnce({ ...request, signal: finalController.signal }, true);
        if (result !== null) return result;
        throw new APIError(409, 'Identity mutation did not commit.', { code: 'identity_mutation_not_committed' });
    } catch (error) {
        if (finalController.signal.aborted && !request.signal.aborted) throw new APIError(503, 'Identity mutation result remains unknown.', { code: 'identity_mutation_result_unknown' });
        throw ensureError(error);
    } finally {
        globalThis.clearTimeout(timeout);
        request.signal.removeEventListener('abort', abortFinal);
    }
};

export { runIdentityMutationWithStatusRecovery };
export type { IdentityMutationPollingRequest };
