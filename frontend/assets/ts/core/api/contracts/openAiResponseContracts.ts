/* SoAI - Frontend OpenAI response boundary decoders [frontend/assets/ts/core/api/contracts/openAiResponseContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { OpenAiChatCompletionChoice, OpenAiChatCompletionResponse, OpenAiChatMessage, OpenAiCompletionChoice, OpenAiCompletionResponse, OpenAiEmbedding, OpenAiEmbeddingResponse, OpenAiEmbeddingUsage, OpenAiImageData, OpenAiImageResponse, OpenAiImageTokenDetails, OpenAiImageUsage, OpenAiTranscriptionResponse, OpenAiUsage } from '@core/api/contracts/openAiResponseContractTypes.ts';
import { readNullableFiniteNumberValue, readRequiredFiniteNumberValue, readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredEnumValue, readRequiredStringValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

const decodeRecordArray = (value: JsonValue | undefined, label: string, optional = false): JsonObject[] => {
    if (optional && (value === null || value === undefined)) return [];
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
    return value.map((entry, index) => requireRecord(entry, `${label}[${String(index)}]`));
};

const decodeNullableRecord = (value: JsonValue | undefined, label: string): JsonObject | null => {
    if (value === null || value === undefined) return null;
    return requireRecord(value, label);
};

const decodeUsage = (value: JsonValue | undefined, label: string): OpenAiUsage => {
    const record = requireRecord(value, label);
    return {
        promptTokens: readRequiredNonNegativeIntegerValue(record['prompt_tokens'], `${label}.prompt_tokens`),
        completionTokens: readRequiredNonNegativeIntegerValue(record['completion_tokens'], `${label}.completion_tokens`),
        totalTokens: readRequiredNonNegativeIntegerValue(record['total_tokens'], `${label}.total_tokens`),
        promptTokensDetails: decodeNullableRecord(record['prompt_tokens_details'], `${label}.prompt_tokens_details`),
        completionTokensDetails: decodeNullableRecord(record['completion_tokens_details'], `${label}.completion_tokens_details`)
    };
};

const decodeNullableUsage = (value: JsonValue | undefined, label: string): OpenAiUsage | null => {
    if (value === null || value === undefined) return null;
    return decodeUsage(value, label);
};

const decodeChatMessage = (value: JsonValue | undefined, label: string): OpenAiChatMessage => {
    const record = requireRecord(value, label);
    return {
        role: readRequiredEnumValue(record['role'], `${label}.role`, ['assistant']),
        content: record['content'] === null ? null : readRequiredStringValue(record['content'], `${label}.content`),
        refusal: readNullableTrimmedStringValue(record['refusal'], `${label}.refusal`),
        toolCalls: decodeRecordArray(record['tool_calls'], `${label}.tool_calls`, true),
        annotations: decodeRecordArray(record['annotations'], `${label}.annotations`, true),
        audio: decodeNullableRecord(record['audio'], `${label}.audio`)
    };
};

const decodeChatChoice = (value: JsonValue, index: number): OpenAiChatCompletionChoice => {
    const label = `OpenAI chat response.choices[${String(index)}]`;
    const record = requireRecord(value, label);
    return {
        index: readRequiredNonNegativeIntegerValue(record['index'], `${label}.index`),
        message: decodeChatMessage(record['message'], `${label}.message`),
        finishReason: readNullableTrimmedStringValue(record['finish_reason'], `${label}.finish_reason`),
        logprobs: decodeNullableRecord(record['logprobs'], `${label}.logprobs`)
    };
};

const decodeOpenAiChatResponse = (value: ApiResponsePayload): OpenAiChatCompletionResponse => {
    const label = 'OpenAI chat response';
    const record = requireRecord(value, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        object: readRequiredEnumValue(record['object'], `${label}.object`, ['chat.completion']),
        created: readRequiredNonNegativeIntegerValue(record['created'], `${label}.created`),
        model: readRequiredTrimmedString(record, 'model', `${label}.model`),
        choices: decodeRecordArray(record['choices'], `${label}.choices`).map(decodeChatChoice),
        usage: decodeNullableUsage(record['usage'], `${label}.usage`),
        systemFingerprint: readNullableTrimmedStringValue(record['system_fingerprint'], `${label}.system_fingerprint`),
        serviceTier: readNullableTrimmedStringValue(record['service_tier'], `${label}.service_tier`)
    };
};

const decodeCompletionChoice = (value: JsonValue, index: number): OpenAiCompletionChoice => {
    const label = `OpenAI completion response.choices[${String(index)}]`;
    const record = requireRecord(value, label);
    return {
        text: readRequiredStringValue(record['text'], `${label}.text`),
        index: readRequiredNonNegativeIntegerValue(record['index'], `${label}.index`),
        logprobs: decodeNullableRecord(record['logprobs'], `${label}.logprobs`),
        finishReason: readNullableTrimmedStringValue(record['finish_reason'], `${label}.finish_reason`)
    };
};

const decodeOpenAiCompletionResponse = (value: ApiResponsePayload): OpenAiCompletionResponse => {
    const label = 'OpenAI completion response';
    const record = requireRecord(value, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        object: readRequiredEnumValue(record['object'], `${label}.object`, ['text_completion']),
        created: readRequiredNonNegativeIntegerValue(record['created'], `${label}.created`),
        model: readRequiredTrimmedString(record, 'model', `${label}.model`),
        choices: decodeRecordArray(record['choices'], `${label}.choices`).map(decodeCompletionChoice),
        usage: decodeNullableUsage(record['usage'], `${label}.usage`),
        systemFingerprint: readNullableTrimmedStringValue(record['system_fingerprint'], `${label}.system_fingerprint`)
    };
};

const decodeEmbedding = (value: JsonValue, index: number): OpenAiEmbedding => {
    const label = `OpenAI embedding response.data[${String(index)}]`;
    const record = requireRecord(value, label);
    const embedding = record['embedding'];
    if (!Array.isArray(embedding)) throw new TypeError(`${label}.embedding must be an array.`);
    return {
        object: readRequiredEnumValue(record['object'], `${label}.object`, ['embedding']),
        embedding: embedding.map((entry, valueIndex) => readRequiredFiniteNumberValue(entry, `${label}.embedding[${String(valueIndex)}]`)),
        index: readRequiredNonNegativeIntegerValue(record['index'], `${label}.index`)
    };
};

const decodeOpenAiEmbeddingResponse = (value: ApiResponsePayload): OpenAiEmbeddingResponse => {
    const label = 'OpenAI embedding response';
    const record = requireRecord(value, label);
    const usageRecord = requireRecord(record['usage'], `${label}.usage`);
    const usage: OpenAiEmbeddingUsage = {
        promptTokens: readRequiredNonNegativeIntegerValue(usageRecord['prompt_tokens'], `${label}.usage.prompt_tokens`),
        totalTokens: readRequiredNonNegativeIntegerValue(usageRecord['total_tokens'], `${label}.usage.total_tokens`)
    };
    return {
        object: readRequiredEnumValue(record['object'], `${label}.object`, ['list']),
        data: decodeRecordArray(record['data'], `${label}.data`).map(decodeEmbedding),
        model: readRequiredTrimmedString(record, 'model', `${label}.model`),
        usage
    };
};

const decodeImageData = (value: JsonValue, index: number): OpenAiImageData => {
    const label = `OpenAI image response.data[${String(index)}]`;
    const record = requireRecord(value, label);
    const url = readNullableTrimmedStringValue(record['url'], `${label}.url`);
    const b64Json = readNullableTrimmedStringValue(record['b64_json'], `${label}.b64_json`);
    if (url === null && b64Json === null) throw new TypeError(`${label} must include url or b64_json.`);
    return { url, b64Json, revisedPrompt: readNullableTrimmedStringValue(record['revised_prompt'], `${label}.revised_prompt`) };
};

const decodeOptionalImageTokenCount = (value: JsonValue | undefined, label: string): number | undefined => (value === undefined ? undefined : readRequiredNonNegativeIntegerValue(value, label));

const decodeImageTokenDetails = (value: JsonValue, label: string): OpenAiImageTokenDetails => {
    const record = requireRecord(value, label);
    const textTokens = decodeOptionalImageTokenCount(record['text_tokens'], `${label}.text_tokens`);
    const imageTokens = decodeOptionalImageTokenCount(record['image_tokens'], `${label}.image_tokens`);
    return {
        ...(textTokens !== undefined ? { textTokens } : {}),
        ...(imageTokens !== undefined ? { imageTokens } : {})
    };
};

const decodeImageUsage = (value: JsonValue | undefined, label: string): OpenAiImageUsage | null => {
    if (value === undefined || value === null) return null;
    const record = requireRecord(value, label);
    const inputTokens = decodeOptionalImageTokenCount(record['input_tokens'], `${label}.input_tokens`);
    const outputTokens = decodeOptionalImageTokenCount(record['output_tokens'], `${label}.output_tokens`);
    const totalTokens = decodeOptionalImageTokenCount(record['total_tokens'], `${label}.total_tokens`);
    const inputTokenDetailsValue = record['input_tokens_details'];
    return {
        ...(inputTokens !== undefined ? { inputTokens } : {}),
        ...(outputTokens !== undefined ? { outputTokens } : {}),
        ...(totalTokens !== undefined ? { totalTokens } : {}),
        ...(inputTokenDetailsValue !== undefined ? { inputTokensDetails: decodeImageTokenDetails(inputTokenDetailsValue, `${label}.input_tokens_details`) } : {})
    };
};

const decodeOpenAiImageResponse = (value: ApiResponsePayload): OpenAiImageResponse => {
    const label = 'OpenAI image response';
    const record = requireRecord(value, label);
    const response: OpenAiImageResponse = {
        created: readRequiredNonNegativeIntegerValue(record['created'], `${label}.created`),
        data: decodeRecordArray(record['data'], `${label}.data`).map(decodeImageData),
        usage: decodeImageUsage(record['usage'], `${label}.usage`)
    };
    return response;
};

const decodeOpenAiTranscriptionResponse = (value: ApiResponsePayload): OpenAiTranscriptionResponse => {
    if (typeof value === 'string') {
        return {
            text: value,
            language: null,
            duration: null,
            words: [],
            segments: [],
            usage: null
        };
    }
    const label = 'OpenAI transcription response';
    const record = requireRecord(value, label);
    const response: OpenAiTranscriptionResponse = {
        text: readRequiredStringValue(record['text'], `${label}.text`),
        language: readNullableTrimmedStringValue(record['language'], `${label}.language`),
        duration: readNullableFiniteNumberValue(record['duration'], `${label}.duration`),
        words: decodeRecordArray(record['words'], `${label}.words`, true),
        segments: decodeRecordArray(record['segments'], `${label}.segments`, true),
        usage: decodeNullableRecord(record['usage'], `${label}.usage`)
    };
    return response;
};

export { decodeOpenAiChatResponse, decodeOpenAiCompletionResponse, decodeOpenAiEmbeddingResponse, decodeOpenAiImageResponse, decodeOpenAiTranscriptionResponse };
export type { OpenAiChatCompletionChoice, OpenAiChatCompletionResponse, OpenAiChatMessage, OpenAiCompletionChoice, OpenAiCompletionResponse, OpenAiEmbedding, OpenAiEmbeddingResponse, OpenAiEmbeddingUsage, OpenAiImageData, OpenAiImageResponse, OpenAiTranscriptionResponse, OpenAiUsage } from '@core/api/contracts/openAiResponseContractTypes.ts';
