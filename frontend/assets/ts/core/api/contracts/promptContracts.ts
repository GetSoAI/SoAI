/* SoAI - Frontend prompt API contracts [frontend/assets/ts/core/api/contracts/promptContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredStringValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface PromptRequest {
    name: string;
    content: string;
    color: string | null;
}

interface PromptResponse {
    id: string;
    userId: number;
    name: string;
    content: string;
    color: string | null;
    createdAtMs: number;
    modifiedAtMs: number;
}

interface PromptBatchDeleteResponse {
    deleted: number;
}

const decodePrompt = (value: JsonValue, label: string): PromptResponse => {
    const record = requireRecord(value, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        userId: readRequiredNonNegativeIntegerValue(record['user_id'], `${label}.user_id`),
        name: readRequiredTrimmedString(record, 'name', `${label}.name`),
        content: readRequiredStringValue(record['content'], `${label}.content`),
        color: readNullableTrimmedStringValue(record['color'], `${label}.color`),
        createdAtMs: readRequiredNonNegativeIntegerValue(record['created_at_ms'], `${label}.created_at_ms`),
        modifiedAtMs: readRequiredNonNegativeIntegerValue(record['modified_at_ms'], `${label}.modified_at_ms`)
    };
};

const decodePromptResponse = (value: ApiResponsePayload): PromptResponse => decodePrompt(requireJsonResponsePayload(value, 'Prompt response'), 'Prompt response');

const decodePromptListResponse = (value: ApiResponsePayload): PromptResponse[] => {
    if (!Array.isArray(value)) throw new TypeError('Prompt list response must be an array.');
    return value.map((entry, index) => decodePrompt(entry, `Prompt list response[${String(index)}]`));
};

const decodePromptBatchDeleteResponse = (value: ApiResponsePayload): PromptBatchDeleteResponse => {
    const record = requireRecord(value, 'Prompt batch delete response');
    return { deleted: readRequiredNonNegativeIntegerValue(record['deleted'], 'Prompt batch delete response.deleted') };
};

const serializePromptRequest = (request: PromptRequest): JsonObject => ({ name: request.name, content: request.content, color: request.color });
const serializePromptBatchDeleteRequest = (ids: string[]): JsonObject => ({ ids });

export { decodePromptBatchDeleteResponse, decodePromptListResponse, decodePromptResponse, serializePromptBatchDeleteRequest, serializePromptRequest };
export type { PromptBatchDeleteResponse, PromptRequest, PromptResponse };
