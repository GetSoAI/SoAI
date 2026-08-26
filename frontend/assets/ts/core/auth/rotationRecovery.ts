/* SoAI - Bounded WebUI session-rotation recovery policy [frontend/assets/ts/core/auth/rotationRecovery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IdentityMutationStatus, IdentityMutationSuccess, SessionRotationRecovery } from '@core/api/contracts/webuiIdentityMutationContracts.ts';
import { APIError, isNetworkError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { wallClockMs } from '@core/time/clock.ts';

interface SelfMutationRecoveryRequest {
    operationId: string;
    execute: ((signal: AbortSignal) => Promise<IdentityMutationSuccess>) | null;
    recover: (signal: AbortSignal) => Promise<SessionRotationRecovery>;
    status: (finalizeAbsence: boolean, signal: AbortSignal) => Promise<IdentityMutationStatus>;
    currentUser: (signal: AbortSignal) => Promise<IdentityMutationSuccess['user']>;
    recoveryDeadlineMs: number;
    finalProbeDeadlineMs: number;
    signal: AbortSignal;
}

interface ClosureRotationRecoveryRequest {
    recover: (signal: AbortSignal) => Promise<SessionRotationRecovery>;
    recoveryDeadlineMs: number;
    finalProbeDeadlineMs: number;
    signal: AbortSignal;
}

const isAmbiguousMutationFailure = (error: Error): boolean => isNetworkError(error) || (error instanceof APIError && error.code === 'identity_mutation_result_unknown');
const isProvisionalNotFound = (error: Error): boolean => error instanceof APIError && error.code === 'user_mutation_not_found';

const delay = async (durationMs: number, signal: AbortSignal): Promise<void> => {
    if (signal.aborted) throw new DOMException('Identity mutation recovery was cancelled.', 'AbortError');
    await new Promise<void>((resolve, reject) => {
        const finish = (): void => {
            signal.removeEventListener('abort', abort);
            resolve();
        };
        const abort = (): void => {
            globalThis.clearTimeout(timer);
            signal.removeEventListener('abort', abort);
            reject(new DOMException('Identity mutation recovery was cancelled.', 'AbortError'));
        };
        const timer = globalThis.setTimeout(finish, durationMs);
        signal.addEventListener('abort', abort, { once: true });
    });
};

const failureFromStatus = (status: Extract<IdentityMutationStatus, { status: 'failed' }>): APIError => new APIError(409, 'Identity mutation failed.', status.traceId === null ? { code: status.errorCode } : { code: status.errorCode, traceId: status.traceId });

const successFromStatus = async (request: SelfMutationRecoveryRequest, status: Extract<IdentityMutationStatus, { status: 'committed' }>): Promise<IdentityMutationSuccess> => ({
    operationId: status.operationId,
    user: await request.currentUser(request.signal)
});

const classifyRecovery = async (request: SelfMutationRecoveryRequest, recovery: SessionRotationRecovery): Promise<IdentityMutationSuccess | null> => {
    if (recovery.status === 'terminal') throw new APIError(401, 'Session rotation is terminal.', { code: 'authentication_error' });
    const operation = recovery.operation;
    if (operation === null || operation.status === 'not_found') return null;
    if (operation.operationId !== request.operationId) throw new APIError(409, 'Identity operation binding changed.', { code: 'operation_id_conflict' });
    if (operation.status === 'failed') throw failureFromStatus(operation);
    return { operationId: request.operationId, user: recovery.user };
};

const probeStatus = async (request: SelfMutationRecoveryRequest, finalizeAbsence: boolean): Promise<IdentityMutationSuccess | null> => {
    try {
        const status = await request.status(finalizeAbsence, request.signal);
        if (status.status === 'not_found') return null;
        if (status.status === 'failed') throw failureFromStatus(status);
        return await successFromStatus(request, status);
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!finalizeAbsence && isProvisionalNotFound(runtimeError)) return null;
        throw runtimeError;
    }
};

const runSelfMutationWithRecovery = async (request: SelfMutationRecoveryRequest): Promise<IdentityMutationSuccess> => {
    if (request.execute !== null) {
        try {
            return await request.execute(request.signal);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isAmbiguousMutationFailure(runtimeError)) throw runtimeError;
        }
    }
    let backoffMs = 250;
    while (wallClockMs() < request.recoveryDeadlineMs) {
        try {
            const recovered = await classifyRecovery(request, await request.recover(request.signal));
            if (recovered !== null) return recovered;
            const statusResult = await probeStatus(request, false);
            if (statusResult !== null) return statusResult;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isNetworkError(runtimeError) && !isProvisionalNotFound(runtimeError)) throw runtimeError;
        }
        const remainingMs = request.recoveryDeadlineMs - wallClockMs();
        if (remainingMs <= 0) break;
        const jitter = 0.8 + Math.random() * 0.4;
        await delay(Math.min(remainingMs, Math.round(backoffMs * jitter)), request.signal);
        backoffMs = Math.min(2_000, backoffMs * 2);
    }
    const finalProbeController = new AbortController();
    const abortFinalProbe = (): void => finalProbeController.abort();
    request.signal.addEventListener('abort', abortFinalProbe, { once: true });
    const finalProbeBudgetMs = Math.max(0, request.finalProbeDeadlineMs - wallClockMs());
    if (finalProbeBudgetMs === 0) throw new APIError(503, 'Identity mutation result remains unknown.', { code: 'identity_mutation_result_unknown' });
    const timeout = globalThis.setTimeout(() => finalProbeController.abort(), finalProbeBudgetMs);
    try {
        const finalRequest: SelfMutationRecoveryRequest = { ...request, signal: finalProbeController.signal };
        const recovered = await classifyRecovery(finalRequest, await finalRequest.recover(finalRequest.signal));
        if (recovered !== null) return recovered;
        const finalized = await probeStatus(finalRequest, true);
        if (finalized !== null) return finalized;
        throw new APIError(409, 'Identity mutation did not commit.', { code: 'identity_mutation_not_committed' });
    } catch (error) {
        const runtimeError = ensureError(error);
        if (finalProbeController.signal.aborted && !request.signal.aborted) throw new APIError(503, 'Identity mutation result remains unknown.', { code: 'identity_mutation_result_unknown' });
        throw runtimeError;
    } finally {
        globalThis.clearTimeout(timeout);
        request.signal.removeEventListener('abort', abortFinalProbe);
    }
};

const recoverSessionFromClosure = async (request: ClosureRotationRecoveryRequest): Promise<IdentityMutationSuccess['user']> => {
    let backoffMs = 250;
    while (wallClockMs() < request.recoveryDeadlineMs) {
        try {
            const response = await request.recover(request.signal);
            if (response.status === 'terminal') throw new APIError(401, 'Session rotation is terminal.', { code: 'authentication_error' });
            return response.user;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isNetworkError(runtimeError)) throw runtimeError;
        }
        const remainingMs = request.recoveryDeadlineMs - wallClockMs();
        if (remainingMs <= 0) break;
        const jitter = 0.8 + Math.random() * 0.4;
        await delay(Math.min(remainingMs, Math.round(backoffMs * jitter)), request.signal);
        backoffMs = Math.min(2_000, backoffMs * 2);
    }
    const finalController = new AbortController();
    const finalBudgetMs = Math.max(0, request.finalProbeDeadlineMs - wallClockMs());
    if (finalBudgetMs === 0) throw new APIError(503, 'Session rotation state remains unknown.', { code: 'identity_mutation_result_unknown' });
    const abortFinal = (): void => finalController.abort();
    request.signal.addEventListener('abort', abortFinal, { once: true });
    const timeout = globalThis.setTimeout(() => finalController.abort(), finalBudgetMs);
    try {
        const response = await request.recover(finalController.signal);
        if (response.status === 'terminal') throw new APIError(401, 'Session rotation is terminal.', { code: 'authentication_error' });
        return response.user;
    } catch (error) {
        if (finalController.signal.aborted && !request.signal.aborted) throw new APIError(503, 'Session rotation state remains unknown.', { code: 'identity_mutation_result_unknown' });
        throw ensureError(error);
    } finally {
        globalThis.clearTimeout(timeout);
        request.signal.removeEventListener('abort', abortFinal);
    }
};

export { recoverSessionFromClosure, runSelfMutationWithRecovery };
export type { ClosureRotationRecoveryRequest, SelfMutationRecoveryRequest };
