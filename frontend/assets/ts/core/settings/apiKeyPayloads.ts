/* SoAI - Shared settings API key payloads [frontend/assets/ts/core/settings/apiKeyPayloads.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiKey } from '@core/settings/contracts.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import { readOptionalRecordArrayField, readRequiredTrimmedStringField } from '@core/types/payloadFieldReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { readOptionalBooleanValue, readOptionalFiniteNumberValue, readOptionalStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface ApiKeyUsageRow {
    keyId: string;
    label: string;
    prefix: string;
    revoked: boolean;
    expiresAtMs: number | null;
    lastUsedAtMs: number | null;
    requestCount: number;
    rateLimitedCount: number;
}

const readAssignedUserId = (value: JsonValue | null | undefined, label: string): number | null => {
    const normalized = readOptionalFiniteNumberValue(value, label);
    if (normalized === undefined) {
        return null;
    }
    return Math.trunc(normalized);
};

const readOptionalScopes = (value: JsonValue | null | undefined, label: string): string[] | undefined => {
    const normalized = readNullableStringArrayValue(value, label);
    if (normalized === null) {
        return undefined;
    }
    return normalized;
};

const readNonNegativeCount = (value: JsonValue | null | undefined, label: string): number => {
    const normalized = readOptionalFiniteNumberValue(value, label);
    if (normalized === undefined || normalized <= 0) {
        return 0;
    }
    return Math.trunc(normalized);
};

const readOptionalPositiveTimestamp = (value: JsonValue | null | undefined, label: string): number | null => {
    const normalized = readOptionalFiniteNumberValue(value, label);
    if (normalized === undefined || normalized <= 0) {
        return null;
    }
    return Math.trunc(normalized);
};

const normalizeApiKeyEntry = (value: JsonValue | null | undefined, index: number): ApiKey => {
    const record = requireRecord(value, `API key entry at index ${String(index)}`);
    const keyId = readRequiredTrimmedStringField(record, 'key_id', `API key entry at index ${String(index)} key_id`);
    const label = readOptionalStringValue(record['label'], `API key entry ${keyId} label`);
    const prefix = readOptionalStringValue(record['prefix'], `API key entry ${keyId} prefix`);
    const revoked = readOptionalBooleanValue(record['revoked'], `API key entry ${keyId} revoked`);
    const expiresAtMs = readOptionalFiniteNumberValue(record['expires_at_ms'], `API key entry ${keyId} expires_at_ms`);
    const rotationDue = readOptionalBooleanValue(record['rotation_due'], `API key entry ${keyId} rotation_due`);
    const createdAtMs = readOptionalFiniteNumberValue(record['created_at_ms'], `API key entry ${keyId} created_at_ms`);
    const lastUsedAtMs = readOptionalFiniteNumberValue(record['last_used_at_ms'], `API key entry ${keyId} last_used_at_ms`);
    const requestCount = readOptionalFiniteNumberValue(record['request_count'], `API key entry ${keyId} request_count`);
    const assignedUserId = readAssignedUserId(record['assigned_user_id'], `API key entry ${keyId} assigned_user_id`);
    const scopes = readOptionalScopes(record['scopes'], `API key entry ${keyId} scopes`);

    return {
        keyId: keyId,
        ...(label ? { label } : {}),
        ...(prefix ? { prefix } : {}),
        ...(revoked === undefined ? {} : { revoked }),
        ...(expiresAtMs === undefined ? {} : { expiresAtMs: expiresAtMs }),
        ...(rotationDue === undefined ? {} : { rotationDue: rotationDue }),
        ...(scopes ? { scopes } : {}),
        ...(createdAtMs === undefined ? {} : { createdAtMs: createdAtMs }),
        ...(lastUsedAtMs === undefined ? {} : { lastUsedAtMs: lastUsedAtMs }),
        ...(requestCount === undefined ? {} : { requestCount: requestCount }),
        ...(assignedUserId === null ? {} : { assignedUserId: assignedUserId })
    };
};

const normalizeApiKeysListResponse = (value: ApiResponsePayload): ApiKey[] => {
    const payload = requireJsonResponsePayload(value, 'API keys list');
    if (payload === null) {
        return [];
    }
    const record = requireRecord(payload, 'API keys list response');
    const entries = readOptionalRecordArrayField(record, 'keys', 'API keys list response.keys');
    return entries.map((entry, index) => normalizeApiKeyEntry(entry, index));
};

const normalizeApiKeyUsageRow = (value: JsonValue | null | undefined, index: number): ApiKeyUsageRow => {
    const record = requireRecord(value, `API key usage entry at index ${String(index)}`);
    const keyId = readRequiredTrimmedStringField(record, 'key_id', `API key usage entry at index ${String(index)} key_id`);
    return {
        keyId: keyId,
        label: readOptionalStringValue(record['label'], `API key usage entry ${keyId} label`) || '',
        prefix: readOptionalStringValue(record['prefix'], `API key usage entry ${keyId} prefix`) || '',
        revoked: readOptionalBooleanValue(record['revoked'], `API key usage entry ${keyId} revoked`) === true,
        expiresAtMs: readOptionalPositiveTimestamp(record['expires_at_ms'], `API key usage entry ${keyId} expires_at_ms`),
        lastUsedAtMs: readOptionalPositiveTimestamp(record['last_used_at_ms'], `API key usage entry ${keyId} last_used_at_ms`),
        requestCount: readNonNegativeCount(record['request_count'], `API key usage entry ${keyId} request_count`),
        rateLimitedCount: readNonNegativeCount(record['rate_limited_count'], `API key usage entry ${keyId} rate_limited_count`)
    };
};

const normalizeApiKeyUsageSnapshot = (value: JsonValue | null | undefined): ApiKeyUsageRow[] => {
    if (value === null) {
        return [];
    }
    const record = requireRecord(value, 'API key usage snapshot');
    const entries = readOptionalRecordArrayField(record, 'keys', 'API key usage snapshot.keys');
    return entries.map((entry, index) => normalizeApiKeyUsageRow(entry, index));
};

export { normalizeApiKeyEntry, normalizeApiKeyUsageSnapshot, normalizeApiKeysListResponse };
export type { ApiKeyUsageRow };
