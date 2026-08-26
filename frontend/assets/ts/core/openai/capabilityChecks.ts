/* SoAI - Shared OpenAI capability checks [frontend/assets/ts/core/openai/capabilityChecks.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isBoolean, isNumber, isString } from '@core/typeGuards.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { OpenAICategory } from '@core/openai/capabilityCategories.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface OpenAIEndpointCapabilityEntry {
    openaiCapabilities?: JsonValue | null | undefined;
}

const normalizeOpenAICapabilityToken = (value: string): string => value.trim().toLowerCase();

const normalizeCapabilityBoolean = (value: JsonValue | undefined): boolean => {
    if (isBoolean(value)) {
        return value;
    }
    if (isNumber(value)) {
        return value !== 0;
    }
    if (isString(value)) {
        const lowered = value.trim().toLowerCase();
        if (!lowered) {
            return false;
        }
        if (lowered === '1' || lowered === 'true' || lowered === 'yes' || lowered === 'on') {
            return true;
        }
        if (lowered === '0' || lowered === 'false' || lowered === 'no' || lowered === 'off') {
            return false;
        }
        return true;
    }
    return Boolean(value);
};

const isOpenAICapabilityEnabled = (openai: JsonObject | null | undefined, category: OpenAICategory, token: string): boolean => {
    if (!isJsonObject(openai)) {
        return false;
    }
    const normalizedToken = normalizeOpenAICapabilityToken(token);
    if (!normalizedToken) {
        return false;
    }
    const flatValue = openai[normalizedToken];
    if (flatValue !== undefined) {
        return normalizeCapabilityBoolean(flatValue);
    }
    const section = openai[category];
    if (!isJsonObject(section)) {
        return false;
    }
    if (!(normalizedToken in section)) {
        return false;
    }
    return normalizeCapabilityBoolean(section[normalizedToken]);
};

const hasOpenAIModality = (modalities: JsonValue | undefined | null, token: string): boolean => {
    if (!isJsonArray(modalities)) {
        return false;
    }
    const normalizedToken = normalizeOpenAICapabilityToken(token);
    if (!normalizedToken) {
        return false;
    }
    for (const entry of modalities) {
        if (!isString(entry)) {
            continue;
        }
        if (normalizeOpenAICapabilityToken(entry) === normalizedToken) {
            return true;
        }
    }
    return false;
};

const supportsOpenAIInputFeatureForModel = (model: ModelData | null, modalityToken: string, capabilityToken: string): boolean => {
    if (!model) {
        return false;
    }
    if (!hasOpenAIModality(model.modalities ?? null, modalityToken)) {
        return false;
    }
    const capabilities = model.openaiCapabilities;
    if (!isJsonObject(capabilities)) {
        return true;
    }
    return isOpenAICapabilityEnabled(capabilities, 'chat_features', capabilityToken);
};

const supportsVisionInputForModel = (model: ModelData | null): boolean => supportsOpenAIInputFeatureForModel(model, 'vision', 'vision');

const supportsOpenAIEndpointForEntry = (entry: OpenAIEndpointCapabilityEntry | null, endpointToken: string, defaultWhenCapabilitiesMissing = false): boolean => {
    if (!entry) {
        return false;
    }
    const capabilities = entry.openaiCapabilities;
    if (!isJsonObject(capabilities)) {
        return defaultWhenCapabilitiesMissing;
    }
    return isOpenAICapabilityEnabled(capabilities, 'endpoints', endpointToken);
};

const supportsOpenAIEndpointForModel = (model: ModelData | null, endpointToken: string): boolean => supportsOpenAIEndpointForEntry(model, endpointToken);

export { hasOpenAIModality, isOpenAICapabilityEnabled, normalizeOpenAICapabilityToken, supportsOpenAIEndpointForEntry, supportsOpenAIEndpointForModel, supportsVisionInputForModel };
export type { OpenAICategory };
