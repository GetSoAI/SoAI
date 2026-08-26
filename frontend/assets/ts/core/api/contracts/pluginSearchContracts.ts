/* SoAI - Frontend plugin model search contracts [frontend/assets/ts/core/api/contracts/pluginSearchContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readNullableFiniteNumberValue, readNullableNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface RemoteModelSearchVariant {
    id: string;
    name: string;
    uri: string;
    sizeBytes: number | null;
    quantization: string | null;
    checksum: string | null;
    extra: JsonObject;
}

interface RemoteModelSearchResult {
    id: string;
    name: string;
    source: string;
    summary: string | null;
    score: number | null;
    tags: string[];
    metadata: JsonObject;
    variants: RemoteModelSearchVariant[];
}

const decodeStringArray = (value: JsonValue | undefined, label: string): string[] => {
    if (value === undefined) return [];
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
    return value.map((entry, index) => readRequiredTrimmedString({ entry }, 'entry', `${label}[${String(index)}]`));
};

const decodeVariant = (value: JsonValue, index: number): RemoteModelSearchVariant => {
    const label = `Remote model search response.variants[${String(index)}]`;
    const record = requireRecord(value, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        name: readRequiredTrimmedString(record, 'name', `${label}.name`),
        uri: readRequiredTrimmedString(record, 'uri', `${label}.uri`),
        sizeBytes: readNullableNonNegativeIntegerValue(record['size_bytes'], `${label}.size_bytes`),
        quantization: readNullableTrimmedStringValue(record['quantization'], `${label}.quantization`),
        checksum: readNullableTrimmedStringValue(record['checksum'], `${label}.checksum`),
        extra: record['extra'] === undefined ? {} : requireRecord(record['extra'], `${label}.extra`)
    };
};

const decodeSearchResult = (value: JsonValue, index: number): RemoteModelSearchResult => {
    const label = `Remote model search response[${String(index)}]`;
    const record = requireRecord(value, label);
    const variants = record['variants'];
    if (variants !== undefined && !Array.isArray(variants)) throw new TypeError(`${label}.variants must be an array.`);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        name: readRequiredTrimmedString(record, 'name', `${label}.name`),
        source: readRequiredTrimmedString(record, 'source', `${label}.source`),
        summary: readNullableTrimmedStringValue(record['summary'], `${label}.summary`),
        score: readNullableFiniteNumberValue(record['score'], `${label}.score`),
        tags: decodeStringArray(record['tags'], `${label}.tags`),
        metadata: record['metadata'] === undefined ? {} : requireRecord(record['metadata'], `${label}.metadata`),
        variants: variants?.map(decodeVariant) ?? []
    };
};

const decodeRemoteModelSearchResponse = (value: ApiResponsePayload): RemoteModelSearchResult[] => {
    if (!Array.isArray(value)) throw new TypeError('Remote model search response must be an array.');
    return value.map(decodeSearchResult);
};

export { decodeRemoteModelSearchResponse };
export type { RemoteModelSearchResult, RemoteModelSearchVariant };
