/* SoAI - Shared chat request parameters [frontend/assets/ts/core/chat/parameters/chatRequestParameters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatParameters } from '@core/chat/parameters/types.ts';
import { BACKEND_OWNED_CHAT_PARAMETER_KEYS, CHAT_PARAMETER_SEND_CONTROLS, CHAT_PARAMETER_WIRE_KEYS, STORED_CHAT_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

const cloneParameterValue = (value: JsonValue): JsonValue => {
    if (Array.isArray(value)) {
        return [...value];
    }
    return value;
};

const resolveSendFlag = (key: string): string | null => {
    for (const control of CHAT_PARAMETER_SEND_CONTROLS) {
        if (control.parameter === key) {
            return control.flag;
        }
    }
    return null;
};

const isSendDisabled = (parameters: ChatParameters, key: string): boolean => {
    const flag = resolveSendFlag(key);
    return flag !== null && parameters[flag] === false;
};

const buildChatRequestParameters = (parameters: ChatParameters, excludedRequestParameters: ReadonlySet<string>): Record<string, JsonValue> => {
    const result: Record<string, JsonValue> = {};
    for (const key of BACKEND_OWNED_CHAT_PARAMETER_KEYS) {
        if (excludedRequestParameters.has(key)) {
            continue;
        }
        if (key === 'logprobs' || key === 'topLogprobs') {
            continue;
        }
        if (isSendDisabled(parameters, key)) {
            continue;
        }
        const value = parameters[key];
        if (value === undefined || value === null) {
            continue;
        }
        result[CHAT_PARAMETER_WIRE_KEYS[key] ?? key] = cloneParameterValue(value);
    }
    if (parameters.logprobsSendEnabled === true && !excludedRequestParameters.has('logprobs')) {
        result['logprobs'] = true;
        if (!excludedRequestParameters.has('topLogprobs') && parameters.topLogprobs !== undefined && parameters.topLogprobs !== null) {
            result['top_logprobs'] = parameters.topLogprobs;
        }
    }
    return result;
};

const buildStoredChatParameters = (parameters: ChatParameters): Record<string, JsonValue> => {
    const result: Record<string, JsonValue> = {};
    for (const key of STORED_CHAT_PARAMETER_KEYS) {
        const value = parameters[key];
        if (value === undefined || value === null) {
            continue;
        }
        result[key] = cloneParameterValue(value);
    }
    return result;
};

const serializeChatParameters = (parameters: ChatParameters): JsonObject => {
    const serialized: JsonObject = {};
    for (const [key, value] of Object.entries(parameters)) {
        if (value !== undefined) {
            serialized[CHAT_PARAMETER_WIRE_KEYS[key] ?? key] = cloneParameterValue(value);
        }
    }
    return serialized;
};

export { buildChatRequestParameters, buildStoredChatParameters, serializeChatParameters };
