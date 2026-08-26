/* SoAI - Frontend API key management contracts [frontend/assets/ts/core/api/contracts/apiKeyContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { ApiKey } from '@core/settings/contracts.ts';
import { normalizeApiKeyEntry } from '@core/settings/apiKeyPayloads.ts';
import { readRequiredRecordArrayField } from '@core/types/payloadFieldReaders.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface ApiKeyCreateRequest {
    label?: string | null;
    scopes?: string[] | null;
    expiresInDays?: number | null;
    expiresAtMs?: number | null;
    rotationReminderInDays?: number | null;
}

interface ApiKeySecretResponse {
    key: string;
    metadata: ApiKey;
}

interface ApiKeyRevokeResponse {
    key: ApiKey;
}

interface ApiKeyDeleteAllResponse {
    deleted: number;
}

interface ApiKeyAssignmentResponse {
    keyId: string;
    assignedUserId: number;
}

const decodeApiKeyListResponse = (value: ApiResponsePayload): ApiKey[] => {
    const record = requireRecord(requireJsonResponsePayload(value, 'API keys list'), 'API keys list response');
    return readRequiredRecordArrayField(record, 'keys', 'API keys list response.keys').map(normalizeApiKeyEntry);
};

const decodeApiKeySecretResponse = (value: ApiResponsePayload, label: string): ApiKeySecretResponse => {
    const record = requireRecord(requireJsonResponsePayload(value, label), label);
    return {
        key: readRequiredTrimmedString(record, 'key', `${label}.key`),
        metadata: normalizeApiKeyEntry(record['metadata'], 0)
    };
};

const decodeApiKeyRevokeResponse = (value: ApiResponsePayload): ApiKeyRevokeResponse => {
    const record = requireRecord(requireJsonResponsePayload(value, 'API key revoke response'), 'API key revoke response');
    return { key: normalizeApiKeyEntry(record['key'], 0) };
};

const decodeApiKeyDeleteAllResponse = (value: ApiResponsePayload): ApiKeyDeleteAllResponse => {
    const record = requireRecord(requireJsonResponsePayload(value, 'API key delete-all response'), 'API key delete-all response');
    return { deleted: readRequiredNonNegativeIntegerValue(record['deleted'], 'API key delete-all response.deleted') };
};

const decodeApiKeyAssignmentResponse = (value: ApiResponsePayload): ApiKeyAssignmentResponse => {
    const record = requireRecord(requireJsonResponsePayload(value, 'API key assignment response'), 'API key assignment response');
    return {
        keyId: readRequiredTrimmedString(record, 'key_id', 'API key assignment response.key_id'),
        assignedUserId: readRequiredNonNegativeIntegerValue(record['assigned_user_id'], 'API key assignment response.assigned_user_id')
    };
};

const serializeApiKeyCreateRequest = (request: ApiKeyCreateRequest): JsonObject => {
    const serialized: JsonObject = {};
    if (request.label !== undefined) serialized['label'] = request.label;
    if (request.scopes !== undefined) serialized['scopes'] = request.scopes;
    if (request.expiresInDays !== undefined) serialized['expires_in_days'] = request.expiresInDays;
    if (request.expiresAtMs !== undefined) serialized['expires_at_ms'] = request.expiresAtMs;
    if (request.rotationReminderInDays !== undefined) serialized['rotation_reminder_in_days'] = request.rotationReminderInDays;
    return serialized;
};

const serializeApiKeyAssignmentRequest = (userId: number): JsonObject => ({ 'user_id': userId });

export { decodeApiKeyAssignmentResponse, decodeApiKeyDeleteAllResponse, decodeApiKeyListResponse, decodeApiKeyRevokeResponse, decodeApiKeySecretResponse, serializeApiKeyAssignmentRequest, serializeApiKeyCreateRequest };
export type { ApiKeyAssignmentResponse, ApiKeyCreateRequest, ApiKeyDeleteAllResponse, ApiKeyRevokeResponse, ApiKeySecretResponse };
