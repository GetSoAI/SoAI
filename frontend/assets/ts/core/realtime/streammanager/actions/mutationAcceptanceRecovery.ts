/* SoAI - Durable keyed mutation acceptance recovery [frontend/assets/ts/core/realtime/streammanager/actions/mutationAcceptanceRecovery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { StreamTaskRuntimeWebSocketClient } from '@core/realtime/streammanager/actions/types.ts';
import type { OperationMetadata } from '@core/realtime/streammanager/types.ts';
import { isObject } from '@core/typeGuards.ts';

class MutationAcceptanceRecoveryRequiredError extends Error {
    readonly code = 'mutation_acceptance_recovery_required';
    readonly operationKey: string;
    readonly requestId: string;

    constructor(operationKey: string, requestId: string) {
        super(`Mutation acceptance could not be verified for request ${requestId}`);
        this.name = 'MutationAcceptanceRecoveryRequiredError';
        this.operationKey = operationKey;
        this.requestId = requestId;
    }
}

const isMutationAcceptanceRecoveryRequiredError = (error: Error): error is MutationAcceptanceRecoveryRequiredError => error instanceof MutationAcceptanceRecoveryRequiredError;

const recoverMutationAcceptance = async (ws: StreamTaskRuntimeWebSocketClient | null, operation: Partial<OperationMetadata> | null, originalError: Error): Promise<string> => {
    const operationKey = toTrimmedString(operation?.['operationKey']);
    const requestId = toTrimmedString(operation?.['requestId']);
    if (!operationKey || !requestId) throw originalError;
    if (!ws) throw new MutationAcceptanceRecoveryRequiredError(operationKey, requestId);
    try {
        const response = await ws.requestSnapshot('tasks.by_id', { 'task_id': requestId });
        if (response?.data === null || response?.data === undefined) {
            throw new MutationAcceptanceRecoveryRequiredError(operationKey, requestId);
        }
        if (!isObject(response.data)) {
            throw new MutationAcceptanceRecoveryRequiredError(operationKey, requestId);
        }
        const snapshotTaskId = toTrimmedString(response.data['task_id']);
        if (snapshotTaskId !== requestId) {
            throw new MutationAcceptanceRecoveryRequiredError(operationKey, requestId);
        }
        return requestId;
    } catch (error) {
        if (error instanceof MutationAcceptanceRecoveryRequiredError) throw error;
        throw new MutationAcceptanceRecoveryRequiredError(operationKey, requestId);
    }
};

export { MutationAcceptanceRecoveryRequiredError, isMutationAcceptanceRecoveryRequiredError, recoverMutationAcceptance };
