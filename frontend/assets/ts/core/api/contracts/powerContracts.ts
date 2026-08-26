/* SoAI - Shared frontend API contract boundary power contracts [frontend/assets/ts/core/api/contracts/powerContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { readNullableNonNegativeIntegerValue, readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredEnumValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';

const POWER_OPERATION_STATUSES: readonly ['scheduled', 'executing', 'completed', 'failed', 'cancelled'] = Object.freeze(['scheduled', 'executing', 'completed', 'failed', 'cancelled']);
type PowerOperationStatus = (typeof POWER_OPERATION_STATUSES)[number];

interface ApplicationRestartResponse {
    status: 'accepted';
    message: string;
    delay: null;
    operationId: null;
}

interface AcceptedPowerActionResponse {
    status: 'accepted';
    operationId: string;
    action: string;
    executeAtMs: number;
}

interface PowerOperationResponse extends JsonObject {
    operationId: string;
    ownerId: number;
    action: string;
    force: boolean;
    acceptedAtMs: number;
    executeAtMs: number;
    status: PowerOperationStatus;
    attemptCount: number;
    dispatchStartedAtMs: number | null;
    completedAtMs: number | null;
    resultCode: string | null;
    errorCode: string | null;
}

const decodeAcceptedPowerActionResponse = (value: ApiResponsePayload): AcceptedPowerActionResponse => {
    const record = requireRecord(value, 'Power action acceptance');
    const status = readRequiredTrimmedString(record, 'status', 'Power action acceptance.status');
    if (status !== 'accepted') throw new TypeError('Power action acceptance.status must be accepted');
    return {
        status,
        operationId: readRequiredTrimmedString(record, 'operation_id', 'Power action acceptance.operation_id'),
        action: readRequiredTrimmedString(record, 'action', 'Power action acceptance.action'),
        executeAtMs: readRequiredNonNegativeIntegerValue(record['execute_at_ms'], 'Power action acceptance.execute_at_ms')
    };
};

const decodeApplicationRestartResponse = (value: ApiResponsePayload): ApplicationRestartResponse => {
    const record = requireRecord(value, 'Application restart response');
    const status = readRequiredTrimmedString(record, 'status', 'Application restart response.status');
    if (status !== 'accepted') throw new TypeError('Application restart response.status must be accepted');
    return {
        status,
        message: readRequiredTrimmedString(record, 'message', 'Application restart response.message'),
        delay: null,
        operationId: null
    };
};

const decodePowerOperationResponse = (value: ApiResponsePayload): PowerOperationResponse => {
    const record = requireRecord(value, 'Power operation response');
    return decodePowerOperationRecord(record, {
        operationId: 'operation_id',
        ownerId: 'owner_id',
        action: 'action',
        force: 'force',
        acceptedAtMs: 'accepted_at_ms',
        executeAtMs: 'execute_at_ms',
        status: 'status',
        attemptCount: 'attempt_count',
        dispatchStartedAtMs: 'dispatch_started_at_ms',
        completedAtMs: 'completed_at_ms',
        resultCode: 'result_code',
        errorCode: 'error_code'
    });
};

const decodePowerOperationResource = (value: ApiResponsePayload): PowerOperationResponse => {
    const record = requireRecord(value, 'Power operation resource');
    return decodePowerOperationRecord(record, {
        operationId: 'operationId',
        ownerId: 'ownerId',
        action: 'action',
        force: 'force',
        acceptedAtMs: 'acceptedAtMs',
        executeAtMs: 'executeAtMs',
        status: 'status',
        attemptCount: 'attemptCount',
        dispatchStartedAtMs: 'dispatchStartedAtMs',
        completedAtMs: 'completedAtMs',
        resultCode: 'resultCode',
        errorCode: 'errorCode'
    });
};

interface PowerOperationFieldNames {
    operationId: string;
    ownerId: string;
    action: string;
    force: string;
    acceptedAtMs: string;
    executeAtMs: string;
    status: string;
    attemptCount: string;
    dispatchStartedAtMs: string;
    completedAtMs: string;
    resultCode: string;
    errorCode: string;
}

const decodePowerOperationRecord = (record: ReturnType<typeof requireRecord>, fields: PowerOperationFieldNames): PowerOperationResponse => {
    return {
        operationId: readRequiredTrimmedString(record, fields.operationId, `Power operation.${fields.operationId}`),
        ownerId: readRequiredNonNegativeIntegerValue(record[fields.ownerId], `Power operation.${fields.ownerId}`),
        action: readRequiredTrimmedString(record, fields.action, `Power operation.${fields.action}`),
        force: readRequiredBooleanValue(record[fields.force], `Power operation.${fields.force}`),
        acceptedAtMs: readRequiredNonNegativeIntegerValue(record[fields.acceptedAtMs], `Power operation.${fields.acceptedAtMs}`),
        executeAtMs: readRequiredNonNegativeIntegerValue(record[fields.executeAtMs], `Power operation.${fields.executeAtMs}`),
        status: readRequiredEnumValue(record[fields.status], `Power operation.${fields.status}`, POWER_OPERATION_STATUSES),
        attemptCount: readRequiredNonNegativeIntegerValue(record[fields.attemptCount], `Power operation.${fields.attemptCount}`),
        dispatchStartedAtMs: readNullableNonNegativeIntegerValue(record[fields.dispatchStartedAtMs], `Power operation.${fields.dispatchStartedAtMs}`),
        completedAtMs: readNullableNonNegativeIntegerValue(record[fields.completedAtMs], `Power operation.${fields.completedAtMs}`),
        resultCode: readNullableTrimmedStringValue(record[fields.resultCode], `Power operation.${fields.resultCode}`),
        errorCode: readNullableTrimmedStringValue(record[fields.errorCode], `Power operation.${fields.errorCode}`)
    };
};

const decodeActivePowerOperationResponse = (value: ApiResponsePayload): PowerOperationResponse | null => {
    return value === null ? null : decodePowerOperationResponse(value);
};

export { decodeAcceptedPowerActionResponse, decodeActivePowerOperationResponse, decodeApplicationRestartResponse, decodePowerOperationResource, decodePowerOperationResponse };
export type { AcceptedPowerActionResponse, ApplicationRestartResponse, PowerOperationResponse, PowerOperationStatus };
