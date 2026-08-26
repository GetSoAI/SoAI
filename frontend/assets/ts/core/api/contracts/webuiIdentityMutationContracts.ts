/* SoAI - WebUI identity mutation API contracts [frontend/assets/ts/core/api/contracts/webuiIdentityMutationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeWebuiUser, type WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireMutationRequestId } from '@core/mutations/mutationIdentity.ts';
import { isIdentityMutationFailureCode, isIdentityMutationType, type IdentityMutationFailureCode, type IdentityMutationType } from '@core/users/identityMutationContract.ts';
import { readRequiredPositiveSafeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredStringValue } from '@core/types/payloadValueReaders.ts';

interface IdentityMutationSuccess {
    operationId: string;
    user: WebuiUser;
}

interface UsernameRenameResult {
    targetUserId: number;
    previousUsername: string;
    newUsername: string;
    identityRevision: number;
}

interface PasswordChangeResult {
    targetUserId: number;
    previousPasswordRevision: number;
    newPasswordRevision: number;
}

type IdentityMutationResult = UsernameRenameResult | PasswordChangeResult;
type IdentityMutationStatus = { status: 'committed'; operationId: string; operationType: IdentityMutationType; result: IdentityMutationResult } | { status: 'failed'; operationId: string; operationType: IdentityMutationType; errorCode: IdentityMutationFailureCode; traceId: string | null } | { status: 'not_found'; operationId: string };

type SessionRotationRecovery = { status: 'active' | 'recovered'; user: WebuiUser; operation: IdentityMutationStatus | null } | { status: 'terminal' };

const readOperationId = (value: ApiResponsePayload, label: string): string => requireMutationRequestId(readRequiredStringValue(value, label));

const readOperationType = (value: ApiResponsePayload, label: string): IdentityMutationType => {
    const text = readRequiredStringValue(value, label);
    if (!isIdentityMutationType(text)) throw new TypeError(`${label} is invalid`);
    return text;
};

const decodeIdentityMutationSuccess = (value: ApiResponsePayload, label: string): IdentityMutationSuccess => {
    const record = requireRecord(value, label);
    return { operationId: readOperationId(record['operation_id'], `${label}.operation_id`), user: decodeWebuiUser(record['user'], `${label}.user`) };
};

const decodeCommittedResult = (value: ApiResponsePayload, operationType: IdentityMutationType): IdentityMutationResult => {
    const record = requireRecord(value, 'Identity mutation result');
    const targetUserId = readRequiredPositiveSafeIntegerValue(record['target_user_id'], 'Identity mutation result.target_user_id');
    if (operationType === 'username_rename') {
        return {
            targetUserId,
            previousUsername: readRequiredStringValue(record['previous_username'], 'Identity mutation result.previous_username'),
            newUsername: readRequiredStringValue(record['new_username'], 'Identity mutation result.new_username'),
            identityRevision: readRequiredPositiveSafeIntegerValue(record['identity_revision'], 'Identity mutation result.identity_revision')
        };
    }
    return {
        targetUserId,
        previousPasswordRevision: readRequiredPositiveSafeIntegerValue(record['previous_password_revision'], 'Identity mutation result.previous_password_revision'),
        newPasswordRevision: readRequiredPositiveSafeIntegerValue(record['new_password_revision'], 'Identity mutation result.new_password_revision')
    };
};

const decodeIdentityMutationStatus = (value: ApiResponsePayload): IdentityMutationStatus => {
    const record = requireRecord(value, 'Identity mutation status');
    const status = readRequiredStringValue(record['status'], 'Identity mutation status.status');
    const operationId = readOperationId(record['operation_id'], 'Identity mutation status.operation_id');
    if (status === 'not_found') return { status, operationId };
    const operationType = readOperationType(record['operation_type'], 'Identity mutation status.operation_type');
    if (status === 'committed') return { status, operationId, operationType, result: decodeCommittedResult(record['result'], operationType) };
    if (status !== 'failed') throw new TypeError('Identity mutation status.status is invalid');
    const errorCode = readRequiredStringValue(record['error_code'], 'Identity mutation status.error_code');
    if (!isIdentityMutationFailureCode(errorCode)) throw new TypeError('Identity mutation status.error_code is invalid');
    const traceValue = record['trace_id'];
    const traceId = traceValue === null || traceValue === undefined ? null : readRequiredStringValue(traceValue, 'Identity mutation status.trace_id');
    return { status, operationId, operationType, errorCode, traceId };
};

const decodeSessionRotationRecovery = (value: ApiResponsePayload): SessionRotationRecovery => {
    const record = requireRecord(value, 'Session rotation recovery');
    const status = readRequiredStringValue(record['status'], 'Session rotation recovery.status');
    if (status === 'terminal') return { status };
    if (status !== 'active' && status !== 'recovered') throw new TypeError('Session rotation recovery.status is invalid');
    const operationValue = record['operation'];
    return { status, user: decodeWebuiUser(record['user'], 'Session rotation recovery.user'), operation: operationValue === null || operationValue === undefined ? null : decodeIdentityMutationStatus(operationValue) };
};

export { decodeIdentityMutationStatus, decodeIdentityMutationSuccess, decodeSessionRotationRecovery };
export type { IdentityMutationResult, IdentityMutationStatus, IdentityMutationSuccess, PasswordChangeResult, SessionRotationRecovery, UsernameRenameResult };
