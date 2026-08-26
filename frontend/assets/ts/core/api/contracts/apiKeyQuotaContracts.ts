/* SoAI - Frontend API key quota contracts [frontend/assets/ts/core/api/contracts/apiKeyQuotaContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { ApiKeyQuotaConfig, ApiKeyQuotaHourlyLimit, ApiKeyQuotaLimit, ApiKeyQuotaMode, ApiKeyQuotaStatus, ApiKeyQuotaSummary, ApiKeyQuotaWindowStatus } from '@core/settings/contracts.ts';
import { readOptionalRecordArrayField, readRequiredTrimmedStringField } from '@core/types/payloadFieldReaders.ts';
import { readRequiredNonNegativeTruncatedIntegerValue, readRequiredPositiveTruncatedIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readNullableJsonObjectValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readAllowedStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface ApiKeyQuotaUpdateRequest {
    mode: ApiKeyQuotaMode;
    hourly?: { limitUnits: number | null; windowHours: number | null } | null;
    daily?: { limitUnits: number | null } | null;
    weekly?: { limitUnits: number | null } | null;
    monthly?: { limitUnits: number | null } | null;
}

const API_KEY_QUOTA_MODES: readonly ApiKeyQuotaMode[] = ['none', 'tokens', 'requests'];
const QUOTA_WINDOWS: readonly ['hourly', 'daily', 'weekly', 'monthly'] = ['hourly', 'daily', 'weekly', 'monthly'];

const decodeQuotaMode = (value: JsonValue | null | undefined, label: string): ApiKeyQuotaMode => {
    const normalized = readRequiredTrimmedStringValue(value, label).toLowerCase();
    const mode = readAllowedStringValue(normalized, API_KEY_QUOTA_MODES);
    if (mode === null) throw new TypeError(`${label} must be one of: none, tokens, requests`);
    return mode;
};

const decodeQuotaLimit = (value: JsonValue | null | undefined, label: string): ApiKeyQuotaLimit | null => {
    const record = readNullableJsonObjectValue(value, label);
    return record === null ? null : { limitUnits: readRequiredPositiveTruncatedIntegerValue(record['limit_units'], `${label}.limit_units`) };
};

const decodeQuotaHourlyLimit = (value: JsonValue | null | undefined, label: string): ApiKeyQuotaHourlyLimit | null => {
    const record = readNullableJsonObjectValue(value, label);
    return record === null
        ? null
        : {
              limitUnits: readRequiredPositiveTruncatedIntegerValue(record['limit_units'], `${label}.limit_units`),
              windowHours: readRequiredPositiveTruncatedIntegerValue(record['window_hours'], `${label}.window_hours`)
          };
};

const decodeQuotaConfig = (value: JsonValue | null | undefined, label: string): ApiKeyQuotaConfig => {
    const record = requireRecord(value, label);
    return {
        mode: decodeQuotaMode(record['mode'], `${label}.mode`),
        hourly: decodeQuotaHourlyLimit(record['hourly'], `${label}.hourly`),
        daily: decodeQuotaLimit(record['daily'], `${label}.daily`),
        weekly: decodeQuotaLimit(record['weekly'], `${label}.weekly`),
        monthly: decodeQuotaLimit(record['monthly'], `${label}.monthly`)
    };
};

const decodeQuotaWindowStatus = (value: JsonValue | null | undefined, label: string): ApiKeyQuotaWindowStatus | null => {
    const record = readNullableJsonObjectValue(value, label);
    if (record === null) return null;
    return {
        limitUnits: readRequiredPositiveTruncatedIntegerValue(record['limit_units'], `${label}.limit_units`),
        usedUnits: readRequiredNonNegativeTruncatedIntegerValue(record['used_units'], `${label}.used_units`),
        reservedUnits: readRequiredNonNegativeTruncatedIntegerValue(record['reserved_units'], `${label}.reserved_units`),
        remainingUnits: readRequiredNonNegativeTruncatedIntegerValue(record['remaining_units'], `${label}.remaining_units`),
        windowStartTsMs: readRequiredNonNegativeTruncatedIntegerValue(record['window_start_ts_ms'], `${label}.window_start_ts_ms`),
        resetAtMs: readRequiredNonNegativeTruncatedIntegerValue(record['reset_at_ms'], `${label}.reset_at_ms`),
        windowMs: readRequiredPositiveTruncatedIntegerValue(record['window_ms'], `${label}.window_ms`)
    };
};

const decodeQuotaStatus = (value: JsonValue | null | undefined, label: string): ApiKeyQuotaStatus => {
    const record = requireRecord(value, label);
    const status: ApiKeyQuotaStatus = { unit: decodeQuotaMode(record['unit'], `${label}.unit`) };
    for (const windowName of QUOTA_WINDOWS) {
        if (windowName in record) status[windowName] = decodeQuotaWindowStatus(record[windowName], `${label}.${windowName}`);
    }
    return status;
};

const decodeApiKeyQuotaSummary = (value: JsonValue | null | undefined, label: string): ApiKeyQuotaSummary => {
    const record = requireRecord(value, label);
    return {
        keyId: readRequiredTrimmedStringField(record, 'key_id', `${label}.key_id`),
        config: decodeQuotaConfig(record['config'], `${label}.config`),
        status: decodeQuotaStatus(record['status'], `${label}.status`)
    };
};

const decodeApiKeyQuotaStatusListResponse = (value: ApiResponsePayload): Record<string, ApiKeyQuotaSummary> => {
    const record = requireRecord(requireJsonResponsePayload(value, 'API key quota status list'), 'API key quota status list response');
    const result: Record<string, ApiKeyQuotaSummary> = {};
    readOptionalRecordArrayField(record, 'keys', 'API key quota status list response.keys').forEach((entry, index) => {
        const summary = decodeApiKeyQuotaSummary(entry, `API key quota status entry at index ${String(index)}`);
        result[summary.keyId] = summary;
    });
    return result;
};

const decodeApiKeyQuotaResponse = (value: ApiResponsePayload): ApiKeyQuotaSummary => decodeApiKeyQuotaSummary(requireJsonResponsePayload(value, 'API key quota'), 'API key quota response');

const serializeQuotaLimit = (limit: { limitUnits: number | null } | null): JsonObject | null => {
    if (limit === null) return null;
    return { 'limit_units': limit.limitUnits };
};

const serializeApiKeyQuotaUpdateRequest = (request: ApiKeyQuotaUpdateRequest): JsonObject => {
    const serialized: JsonObject = { mode: request.mode };
    if (request.hourly !== undefined) {
        serialized['hourly'] = request.hourly === null ? null : { 'limit_units': request.hourly.limitUnits, 'window_hours': request.hourly.windowHours };
    }
    if (request.daily !== undefined) serialized['daily'] = serializeQuotaLimit(request.daily);
    if (request.weekly !== undefined) serialized['weekly'] = serializeQuotaLimit(request.weekly);
    if (request.monthly !== undefined) serialized['monthly'] = serializeQuotaLimit(request.monthly);
    return serialized;
};

export { decodeApiKeyQuotaResponse, decodeApiKeyQuotaStatusListResponse, serializeApiKeyQuotaUpdateRequest };
export type { ApiKeyQuotaUpdateRequest };
