/* SoAI - Identity-safe keyed accepted-task admission [frontend/assets/ts/core/realtime/streammanager/actions/keyedTaskAdmission.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { requireMutationRequestId } from '@core/mutations/mutationIdentity.ts';
import { isMutationAcceptanceRecoveryRequiredError } from '@core/realtime/streammanager/actions/mutationAcceptanceRecovery.ts';
import type { OperationMetadata } from '@core/realtime/streammanager/types.ts';

interface AcceptedTaskDescriptor {
    taskId: string;
    endpoint?: string;
}

interface KeyedTaskAdmissionGate {
    readonly operationKey: string;
    readonly requestId: string;
    readonly promise: Promise<AcceptedTaskDescriptor>;
}

const resolveKeyedTaskAdmission = (gates: Map<string, KeyedTaskAdmissionGate>, operationKeyInput: string, requestIdInput: string, dispatch: (requestId: string) => Promise<AcceptedTaskDescriptor>): Promise<AcceptedTaskDescriptor> => {
    const operationKey = toTrimmedString(operationKeyInput);
    if (!operationKey) throw new Error('Keyed task admission requires an operation key');
    const existing = gates.get(operationKey);
    if (existing) return existing.promise;
    const requestId = requireMutationRequestId(requestIdInput);
    let gate: KeyedTaskAdmissionGate;
    const promise = dispatch(requestId)
        .then((descriptor): AcceptedTaskDescriptor => {
            const acceptedTaskId = toTrimmedString(descriptor.taskId);
            if (acceptedTaskId !== requestId) throw new Error(`Accepted task identity mismatch for ${operationKey}`);
            return descriptor.endpoint === undefined ? { taskId: acceptedTaskId } : { taskId: acceptedTaskId, endpoint: descriptor.endpoint };
        })
        .catch((error): never => {
            const normalizedError = ensureError(error);
            if (!isMutationAcceptanceRecoveryRequiredError(normalizedError) && gates.get(operationKey) === gate) {
                gates.delete(operationKey);
            }
            throw normalizedError;
        });
    gate = { operationKey, requestId, promise };
    gates.set(operationKey, gate);
    return promise;
};

const finalizeKeyedTaskAdmission = (gates: Map<string, KeyedTaskAdmissionGate>, taskIdInput: string): boolean => {
    const taskId = toTrimmedString(taskIdInput);
    if (!taskId) return false;
    for (const [operationKey, gate] of gates.entries()) {
        if (gate.requestId !== taskId) continue;
        if (gates.get(operationKey) === gate) gates.delete(operationKey);
        return true;
    }
    return false;
};

const getKeyedTaskAdmissionId = (gates: Map<string, KeyedTaskAdmissionGate>, operationKeyInput: string): string | null => {
    const operationKey = toTrimmedString(operationKeyInput);
    return operationKey ? (gates.get(operationKey)?.requestId ?? null) : null;
};

const resolveOptionalKeyedTaskAdmission = (gates: Map<string, KeyedTaskAdmissionGate>, operation: Partial<OperationMetadata> | null, dispatch: () => Promise<AcceptedTaskDescriptor>): Promise<AcceptedTaskDescriptor> => {
    const operationKey = toTrimmedString(operation?.['operationKey']);
    const requestId = toTrimmedString(operation?.['requestId']);
    if (!operationKey && !requestId) return dispatch();
    if (!operationKey || !requestId) throw new Error('Mutation task operation requires operationKey and requestId');
    return resolveKeyedTaskAdmission(gates, operationKey, requestId, async () => dispatch());
};

export { finalizeKeyedTaskAdmission, getKeyedTaskAdmissionId, resolveKeyedTaskAdmission, resolveOptionalKeyedTaskAdmission };
export type { AcceptedTaskDescriptor, KeyedTaskAdmissionGate };
