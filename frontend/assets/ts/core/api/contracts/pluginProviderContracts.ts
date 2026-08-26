/* SoAI - Frontend external plugin provider contracts [frontend/assets/ts/core/api/contracts/pluginProviderContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readNullableNonNegativeIntegerValue, readRequiredNonNegativeIntegerValue, readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readNullableStringRecordValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredEnumValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type ExternalProviderStatus = 'UNCHECKED' | 'OK' | 'ERROR' | 'TIMEOUT' | 'VALIDATING' | 'AUTH_REQUIRED';

interface ExternalProviderRecord {
    id: string;
    pluginName: string;
    revision: number;
    name: string | null;
    apiUrl: string | null;
    apiKey: string | null;
    modelsFilter: string[];
    extraHeaders: Record<string, string> | null;
    extraQueryParameters: Record<string, string> | null;
    contextWindowTokens: number | null;
    createdAtMs: number | null;
    lastStatus: ExternalProviderStatus;
    lastError: string | null;
    lastCheckedAtMs: number | null;
}

interface ExternalProviderCreateResponse {
    provider: ExternalProviderRecord;
    validation: JsonObject;
}

const PROVIDER_STATUSES: readonly ExternalProviderStatus[] = ['UNCHECKED', 'OK', 'ERROR', 'TIMEOUT', 'VALIDATING', 'AUTH_REQUIRED'];

const decodeStringArray = (value: JsonValue | undefined, label: string): string[] => {
    if (value === undefined) return [];
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
    return value.map((entry, index) => readRequiredTrimmedString({ entry }, 'entry', `${label}[${String(index)}]`));
};

const decodePositiveInteger = (value: JsonValue | undefined, label: string): number | null => {
    if (value === null || value === undefined) return null;
    return readRequiredPositiveIntegerValue(value, label);
};

const decodeExternalProviderRecord = (value: ApiResponsePayload, label = 'External provider response'): ExternalProviderRecord => {
    const record = requireRecord(value, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        pluginName: readRequiredTrimmedString(record, 'plugin_name', `${label}.plugin_name`),
        revision: readRequiredNonNegativeIntegerValue(record['revision'], `${label}.revision`),
        name: readNullableTrimmedStringValue(record['name'], `${label}.name`),
        apiUrl: readNullableTrimmedStringValue(record['api_url'], `${label}.api_url`),
        apiKey: readNullableTrimmedStringValue(record['api_key'], `${label}.api_key`),
        modelsFilter: decodeStringArray(record['models_filter'], `${label}.models_filter`),
        extraHeaders: readNullableStringRecordValue(record['extra_headers'], `${label}.extra_headers`),
        extraQueryParameters: readNullableStringRecordValue(record['extra_query_params'], `${label}.extra_query_params`),
        contextWindowTokens: decodePositiveInteger(record['context_window_tokens'], `${label}.context_window_tokens`),
        createdAtMs: readNullableNonNegativeIntegerValue(record['created_at_ms'], `${label}.created_at_ms`),
        lastStatus: record['last_status'] === undefined ? 'UNCHECKED' : readRequiredEnumValue(record['last_status'], `${label}.last_status`, PROVIDER_STATUSES),
        lastError: readNullableTrimmedStringValue(record['last_error'], `${label}.last_error`),
        lastCheckedAtMs: readNullableNonNegativeIntegerValue(record['last_checked_at_ms'], `${label}.last_checked_at_ms`)
    };
};

const decodeExternalProviderListResponse = (value: ApiResponsePayload): ExternalProviderRecord[] => {
    if (!Array.isArray(value)) throw new TypeError('External provider list response must be an array.');
    return value.map((entry, index) => decodeExternalProviderRecord(entry, `External provider list response[${String(index)}]`));
};

const decodeExternalProviderCreateResponse = (value: ApiResponsePayload): ExternalProviderCreateResponse => {
    const label = 'External provider create response';
    const record = requireRecord(value, label);
    readRequiredTrimmedString(record, 'message', `${label}.message`);
    return {
        provider: decodeExternalProviderRecord(record['provider'], `${label}.provider`),
        validation: requireRecord(record['validation'], `${label}.validation`)
    };
};

export { decodeExternalProviderCreateResponse, decodeExternalProviderListResponse, decodeExternalProviderRecord };
export type { ExternalProviderCreateResponse, ExternalProviderRecord, ExternalProviderStatus };
