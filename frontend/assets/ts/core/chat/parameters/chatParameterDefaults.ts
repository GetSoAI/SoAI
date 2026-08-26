/* SoAI - Shared chat parameter defaults [frontend/assets/ts/core/chat/parameters/chatParameterDefaults.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNullOrUndefined, isNumber, isString } from '@core/typeGuards.ts';
import type { ChatParameters } from '@core/chat/parameters/types.ts';
import { DEFAULT_AGENT_MAX_ITERATIONS } from '@core/chat/parameters/agentMaxIterations.ts';
import { CHAT_PARAMETER_SEND_FLAG_KEYS, CHAT_PARAMETER_SEND_FLAG_KEY_SET, CHAT_PARAMETER_WIRE_KEYS, CHAT_WIRE_TO_PARAMETER_KEYS, CHAT_PARAMETER_TO_PREFERENCE_MAP, CHAT_PREFERENCE_TO_PARAMETER_MAP, CHAT_PRESET_PARAMETER_KEY_SET, LOCAL_ONLY_CHAT_PARAMETER_KEY_SET } from '@core/chat/parameters/chatParameterKeySets.ts';
import { getParameterMeta } from '@core/chat/parameters/chatParameterMeta.ts';
import { normalizeChatMobileAuxiliaryAction } from '@core/chat/parameters/mobileAuxiliaryAction.ts';
import { isReasoningEffortLevel } from '@core/chat/parameters/reasoningEffort.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isJsonObject, isJsonValue, type JsonRecord, type JsonValue } from '@core/types/jsonValues.ts';

const getDefaultChatParameters = (): ChatParameters => {
    return {
        temperature: 0.7,
        contextWindowTokens: null,
        maxCompletionTokens: null,
        topP: 1.0,
        frequencyPenalty: 0,
        presencePenalty: 0,
        stop: [],
        logprobs: false,
        topLogprobs: null,
        reasoningEffort: null,
        serviceTier: null,
        completionCount: 1,
        reasoningEffortSendEnabled: false,
        maxCompletionTokensSendEnabled: false,
        topPSendEnabled: true,
        frequencyPenaltySendEnabled: true,
        presencePenaltySendEnabled: true,
        stopSendEnabled: false,
        logprobsSendEnabled: false,
        widescreenMode: false,
        richTextEnabled: true,
        inlineMultimediaPreviewsEnabled: true,
        textZoom: 1,
        hideRealModel: false,
        autoTitleGeneration: true,
        hideAutomationRuns: false,
        hideMessagingConversations: false,
        showActivities: true,
        notifyOnCompletion: false,
        notifyOnError: true,
        microphoneSoundEffectsEnabled: true,
        inputActionVoiceEnabled: true,
        inputActionCallEnabled: true,
        inputActionFileUploadEnabled: true,
        inputActionCameraEnabled: false,
        inputActionPromptsEnabled: false,
        inputActionTokenCounterEnabled: true,
        inputActionCharacterMapEnabled: false,
        inputActionMobileAuxiliaryAction: 'attach',
        conversationPdfExportEnabled: true,
        toolsEnabled: true,
        toolApprovalRequired: true,
        newConversationInheritLastSettings: true,
        voiceTtsModel: 'auto',
        voiceSttModel: 'auto',
        voiceTtsVoice: null,
        voiceTtsSpeed: null,
        agentMaxIterations: DEFAULT_AGENT_MAX_ITERATIONS
    };
};

const cloneChatParameters = (source: Partial<ChatParameters> = {}, defaults: ChatParameters = getDefaultChatParameters()): ChatParameters => {
    const cloned: ChatParameters = { ...defaults };
    for (const key of Object.keys(defaults)) {
        const sourceValue = source[key];
        const defaultValue = defaults[key];
        const value = sourceValue !== undefined ? sourceValue : defaultValue;
        cloned[key] = Array.isArray(value) ? [...value] : value;
    }
    return cloned;
};

const normalizeNumericParameter = (parameter: string, rawValue: JsonValue): JsonValue => {
    const meta = getParameterMeta(parameter);
    if (!meta || meta.type !== 'number') return rawValue;
    if (isNullOrUndefined(rawValue) || rawValue === '') {
        throw new Error(`Parameter "${String(parameter)}" requires a numeric value`);
    }
    let numeric = Number(rawValue);
    if (!Number.isFinite(numeric)) {
        throw new Error(`Parameter "${String(parameter)}" must be a finite number`);
    }
    if (isNumber(meta.precision)) {
        const scale = 10 ** meta.precision;
        numeric = Math.round(numeric * scale) / scale;
    }
    numeric = clampNumber(numeric, meta.min, meta.max);
    return numeric;
};

const formatParameterValue = (parameter: string, value: JsonValue | undefined): string => {
    if (!isNumber(value) || !Number.isFinite(value)) return isNullOrUndefined(value) ? '' : String(value);
    const meta = getParameterMeta(parameter);
    if (!meta || meta.type !== 'number' || !isNumber(meta.precision)) return String(value);
    return meta.precision > 0 ? value.toFixed(meta.precision) : String(Math.round(value));
};

const formatParameterForInput = (parameter: string, value: JsonValue | undefined): string => {
    if (isNumber(value)) {
        return formatParameterValue(parameter, value);
    }
    if (value === undefined || value === null) {
        return '';
    }
    return String(value);
};

const normalizeStoredParameterValue = (parameterKey: string, value: JsonValue | undefined, defaults: ChatParameters): JsonValue | undefined => {
    if (value === undefined) return undefined;
    if (parameterKey === 'stop') return Array.isArray(value) && isJsonValue(value) ? [...value] : [];
    if (value === null) return null;
    if (value === '' && parameterKey in defaults) return defaults[parameterKey];
    if (Array.isArray(value) && isJsonValue(value)) return [...value];
    const meta = getParameterMeta(parameterKey);
    if (meta && meta.type === 'number') {
        const numeric = Number(value);
        if (Number.isFinite(numeric)) {
            return normalizeNumericParameter(parameterKey, numeric);
        }
        return defaults[parameterKey];
    }
    if (parameterKey === 'logprobs' || CHAT_PARAMETER_SEND_FLAG_KEY_SET.has(parameterKey)) {
        return String(value).toLowerCase() === 'true' || value === '1' || value === 1;
    }
    if (parameterKey === 'reasoningEffort') {
        const stringValue = isString(value) ? value.toLowerCase() : '';
        return isReasoningEffortLevel(stringValue) ? stringValue : null;
    }
    if (parameterKey === 'serviceTier') {
        const allowed = ['auto', 'default', 'flex', 'priority'];
        const stringValue = isString(value) ? value.toLowerCase() : '';
        return allowed.includes(stringValue) ? stringValue : null;
    }
    if (parameterKey === 'inputActionMobileAuxiliaryAction') {
        return normalizeChatMobileAuxiliaryAction(value);
    }
    return isJsonValue(value) ? value : defaults[parameterKey];
};

const resolveStoredParameters = (preferences: JsonRecord = {}): ChatParameters => {
    const defaults = getDefaultChatParameters();
    const resolved: ChatParameters = { ...defaults };

    const processKey = (parameterKey: string, value: JsonValue | undefined): void => {
        if (value === undefined) return;
        if (!(parameterKey in resolved)) return;
        const normalized = normalizeStoredParameterValue(parameterKey, value, defaults);
        if (normalized !== undefined) resolved[parameterKey] = normalized;
    };

    Object.entries(preferences).forEach(([prefKey, value]) => {
        if (prefKey === 'parameters' || prefKey === 'model') {
            return;
        }
        const mappedParameterKey = CHAT_PREFERENCE_TO_PARAMETER_MAP[prefKey] ?? CHAT_WIRE_TO_PARAMETER_KEYS[prefKey] ?? null;
        const parameterKey = mappedParameterKey ?? prefKey;
        if (!LOCAL_ONLY_CHAT_PARAMETER_KEY_SET.has(parameterKey) && !CHAT_PARAMETER_SEND_FLAG_KEY_SET.has(parameterKey) && !CHAT_PRESET_PARAMETER_KEY_SET.has(parameterKey)) {
            return;
        }
        processKey(parameterKey, value);
    });

    const nested = preferences['parameters'];
    if (isJsonObject(nested)) {
        Object.entries(nested).forEach(([key, value]) => {
            const parameterKey = CHAT_WIRE_TO_PARAMETER_KEYS[key] ?? key;
            if (parameterKey in CHAT_PARAMETER_TO_PREFERENCE_MAP) {
                return;
            }
            if (!LOCAL_ONLY_CHAT_PARAMETER_KEY_SET.has(parameterKey) && !CHAT_PARAMETER_SEND_FLAG_KEY_SET.has(parameterKey) && !CHAT_PRESET_PARAMETER_KEY_SET.has(parameterKey)) {
                return;
            }
            processKey(parameterKey, value);
        });
    }

    return resolved;
};

type ChatPreferencesPayload = JsonRecord & { parameters: JsonRecord };

const buildChatPreferencesPayload = (input: { parameters: ChatParameters }): ChatPreferencesPayload => {
    const parametersPayload: JsonRecord = {};
    const payload: ChatPreferencesPayload = { parameters: parametersPayload };
    const parameters = input.parameters;

    Object.entries(CHAT_PARAMETER_TO_PREFERENCE_MAP).forEach(([parameterKey, prefKey]) => {
        if (LOCAL_ONLY_CHAT_PARAMETER_KEY_SET.has(parameterKey) && parameterKey in parameters) {
            const value = parameters[parameterKey];
            if (value !== undefined) {
                payload[prefKey] = value;
            }
        }
    });

    Object.keys(parameters)
        .sort((left, right) => left.localeCompare(right, 'en'))
        .forEach((key) => {
            if (key in CHAT_PARAMETER_TO_PREFERENCE_MAP) {
                return;
            }
            if (LOCAL_ONLY_CHAT_PARAMETER_KEY_SET.has(key) && key in parameters) {
                const value = parameters[key];
                if (value !== undefined) {
                    parametersPayload[CHAT_PARAMETER_WIRE_KEYS[key] ?? key] = value;
                }
            }
        });

    for (const key of CHAT_PARAMETER_SEND_FLAG_KEYS) {
        if (key in parameters) {
            const value = parameters[key];
            if (value !== undefined) {
                parametersPayload[CHAT_PARAMETER_WIRE_KEYS[key] ?? key] = value;
            }
        }
    }

    return payload;
};

export { buildChatPreferencesPayload, cloneChatParameters, formatParameterForInput, getDefaultChatParameters, normalizeNumericParameter, normalizeStoredParameterValue, resolveStoredParameters };
export type { ChatParameters };
