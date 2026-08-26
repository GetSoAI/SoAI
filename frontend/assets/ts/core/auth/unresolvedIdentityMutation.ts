/* SoAI - Persisted unresolved identity mutation ownership [frontend/assets/ts/core/auth/unresolvedIdentityMutation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StorageInterface } from '@core/auth/types.ts';
import { isMutationRequestId } from '@core/mutations/mutationIdentity.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isIdentityMutationType, type IdentityMutationType } from '@core/users/identityMutationContract.ts';
import { requireCanonicalUsername } from '@core/users/username.ts';

const UNRESOLVED_IDENTITY_MUTATION_KEY = 'unresolved_identity_mutation_v1';

interface UnresolvedIdentityMutation {
    actorId: number;
    operationId: string;
    operationType: IdentityMutationType;
    targetUserId: number;
    requestedUsername: string | null;
    recoveryDeadlineMs: number;
    finalProbeDeadlineMs: number;
    stale: boolean;
}

const isPositiveSafeInteger = (value: JsonValue | undefined): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
const isAbsoluteDeadline = (value: JsonValue | undefined): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;

const parseRequestedUsername = (value: JsonValue | undefined, operationType: IdentityMutationType): string | null => {
    if (operationType === 'password_change') {
        if (value !== null) throw new Error('Persisted password mutation cannot contain a requested username.');
        return null;
    }
    if (typeof value !== 'string') throw new Error('Persisted rename requires a requested username.');
    const canonical = requireCanonicalUsername(value);
    if (canonical !== value) throw new Error('Persisted rename username is not canonical.');
    return canonical;
};

const parseUnresolvedIdentityMutation = (value: JsonValue | null): UnresolvedIdentityMutation | null => {
    if (value === null) return null;
    if (!isJsonObject(value)) throw new Error('Persisted identity mutation is malformed.');
    const actorId = value['actor_id'];
    const operationId = value['operation_id'];
    const operationType = value['operation_type'];
    const targetUserId = value['target_user_id'];
    const recoveryDeadlineMs = value['recovery_deadline_ms'];
    const finalProbeDeadlineMs = value['final_probe_deadline_ms'];
    const stale = value['stale'];
    if (!isPositiveSafeInteger(actorId) || !isPositiveSafeInteger(targetUserId)) throw new Error('Persisted identity mutation user identity is invalid.');
    if (typeof operationId !== 'string' || !isMutationRequestId(operationId)) throw new Error('Persisted identity mutation operation identity is invalid.');
    if (typeof operationType !== 'string' || !isIdentityMutationType(operationType)) throw new Error('Persisted identity mutation type is invalid.');
    if (!isAbsoluteDeadline(recoveryDeadlineMs) || !isAbsoluteDeadline(finalProbeDeadlineMs) || finalProbeDeadlineMs < recoveryDeadlineMs) throw new Error('Persisted identity mutation deadlines are invalid.');
    if (typeof stale !== 'boolean') throw new Error('Persisted identity mutation state is invalid.');
    return { actorId, operationId, operationType, targetUserId, requestedUsername: parseRequestedUsername(value['requested_username'], operationType), recoveryDeadlineMs, finalProbeDeadlineMs, stale };
};

const serializeUnresolvedIdentityMutation = (record: UnresolvedIdentityMutation): JsonObject => ({
    'actor_id': record.actorId,
    'operation_id': record.operationId,
    'operation_type': record.operationType,
    'target_user_id': record.targetUserId,
    'requested_username': record.requestedUsername,
    'recovery_deadline_ms': record.recoveryDeadlineMs,
    'final_probe_deadline_ms': record.finalProbeDeadlineMs,
    stale: record.stale
});

const readUnresolvedIdentityMutation = (storage: StorageInterface): UnresolvedIdentityMutation | null => parseUnresolvedIdentityMutation(storage.get(UNRESOLVED_IDENTITY_MUTATION_KEY, null));
const writeUnresolvedIdentityMutation = async (storage: StorageInterface, record: UnresolvedIdentityMutation): Promise<void> => {
    storage.set(UNRESOLVED_IDENTITY_MUTATION_KEY, serializeUnresolvedIdentityMutation(record));
    await storage.flushPending();
};
const clearUnresolvedIdentityMutation = async (storage: StorageInterface): Promise<void> => {
    storage.remove(UNRESOLVED_IDENTITY_MUTATION_KEY);
    await storage.flushPending();
};

export { clearUnresolvedIdentityMutation, readUnresolvedIdentityMutation, writeUnresolvedIdentityMutation };
export type { UnresolvedIdentityMutation };
