/* SoAI - Shared frontend API contract boundary file contracts [frontend/assets/ts/core/api/contracts/fileContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredEnumValue, readRequiredStringValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type OpenAiFileStatus = 'uploaded' | 'processed' | 'error';

interface OpenAiFileObject {
    id: string;
    object: 'file';
    bytes: number;
    createdAt: number;
    filename: string;
    purpose: string;
    status: OpenAiFileStatus;
    statusDetails: string | null;
}

interface OpenAiFileListResponse {
    object: 'list';
    data: OpenAiFileObject[];
    firstId: string;
    lastId: string;
    hasMore: boolean;
}

interface OpenAiFileDeleteResponse {
    id: string;
    object: 'file.deleted';
    deleted: boolean;
}

const readLiteral = <Literal extends string>(value: JsonValue | undefined, expected: Literal, label: string): Literal => {
    const literal = readRequiredStringValue(value, label);
    if (literal !== expected) {
        throw new TypeError(`${label} must be ${expected}.`);
    }
    return expected;
};

const readStatusDetails = (value: JsonValue | undefined, label: string): string | null => {
    if (value === null) {
        return null;
    }
    return readRequiredStringValue(value, `${label}.status_details`);
};

const decodeFileObject = (value: ApiResponsePayload | JsonValue, label: string = 'OpenAI file response'): OpenAiFileObject => {
    const record = requireRecord(value, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        object: readLiteral(record['object'], 'file', `${label}.object`),
        bytes: readRequiredNonNegativeIntegerValue(record['bytes'], `${label}.bytes`),
        createdAt: readRequiredNonNegativeIntegerValue(record['created_at'], `${label}.created_at`),
        filename: readRequiredTrimmedString(record, 'filename', `${label}.filename`),
        purpose: readRequiredTrimmedString(record, 'purpose', `${label}.purpose`),
        status: readRequiredEnumValue(record['status'], `${label}.status`, ['uploaded', 'processed', 'error']),
        statusDetails: readStatusDetails(record['status_details'], label)
    };
};

const decodeFileListResponse = (value: ApiResponsePayload): OpenAiFileListResponse => {
    const record = requireRecord(value, 'OpenAI file list response');
    const data = record['data'];
    if (!Array.isArray(data)) {
        throw new TypeError('OpenAI file list response.data must be an array.');
    }
    return {
        object: readLiteral(record['object'], 'list', 'OpenAI file list response.object'),
        data: data.map((file, index) => decodeFileObject(file, `OpenAI file list response.data[${String(index)}]`)),
        firstId: readRequiredStringValue(record['first_id'], 'OpenAI file list response.first_id'),
        lastId: readRequiredStringValue(record['last_id'], 'OpenAI file list response.last_id'),
        hasMore: readRequiredBooleanValue(record['has_more'], 'OpenAI file list response.has_more')
    };
};

const decodeFileDeleteResponse = (value: ApiResponsePayload): OpenAiFileDeleteResponse => {
    const record = requireRecord(value, 'OpenAI file deletion response');
    return {
        id: readRequiredTrimmedString(record, 'id', 'OpenAI file deletion response.id'),
        object: readLiteral(record['object'], 'file.deleted', 'OpenAI file deletion response.object'),
        deleted: readRequiredBooleanValue(record['deleted'], 'OpenAI file deletion response.deleted')
    };
};

const decodeFileContentResponse = (value: ApiResponsePayload): Response => {
    if (!(value instanceof Response)) {
        throw new TypeError('OpenAI file content response must be a Response.');
    }
    return value;
};

export { decodeFileContentResponse, decodeFileDeleteResponse, decodeFileListResponse, decodeFileObject };
export type { OpenAiFileDeleteResponse, OpenAiFileListResponse, OpenAiFileObject, OpenAiFileStatus };
