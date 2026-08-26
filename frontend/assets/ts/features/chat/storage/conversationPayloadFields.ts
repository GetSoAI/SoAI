/* SoAI - Chat feature conversation payload fields [frontend/assets/ts/features/chat/storage/conversationPayloadFields.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEpochMsValue } from '@core/time/epochMs.ts';
import { isBoolean, isNumber, isPlainObject, isString } from '@core/typeGuards.ts';
import { normalizeColor } from '@core/ui/colorToolkitBase.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { sanitizeTitle } from '@features/chat/conversationFormatting.ts';
import { parseConversationModelSettings, serializeConversationModelSettings } from '@core/chat/executionSettingsMapping.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';
import type { ConversationModelSettings } from '@core/chat/executionSettingsTypes.ts';

const requireConversationTitle = (value: string, context: string): string => {
    if (!isString(value) || !value.trim()) {
        throw new Error(`${context} title is missing or invalid`);
    }
    const title = sanitizeTitle(value);
    if (!title) {
        throw new Error(`${context} title is missing or invalid`);
    }
    return title;
};

const requireBackendConversationTitle = (value: JsonValue | undefined, context: string): string => {
    if (!isString(value) || !value.trim()) {
        throw new Error(`${context} title is missing or invalid`);
    }
    return sanitizeTitle(value) || value.trim();
};

const requireEpochMs = (value: JsonValue | undefined, field: string, context: string): number => {
    if (!isEpochMsValue(value)) {
        throw new Error(`${context} ${field} is missing or invalid`);
    }
    return value;
};

const parseRequiredModelSettings = (value: JsonValue | undefined, context: string): Conversation['modelSettings'] => {
    if (!isJsonObject(value)) {
        throw new Error(`${context} model_settings is missing or invalid`);
    }
    return parseConversationModelSettings(value);
};

const requireConversationModelSettings = (value: ConversationModelSettings | undefined, context: string): ConversationModelSettings => {
    if (!value || !isPlainObject(value)) {
        throw new Error(`${context} model settings are missing or invalid`);
    }
    return parseConversationModelSettings(serializeConversationModelSettings(value));
};

const requireConversationColor = (value: JsonValue | undefined, context: string): string | null => {
    if (value === null) {
        return null;
    }
    if (!isString(value)) {
        throw new Error(`${context} color is invalid`);
    }
    const normalized = normalizeColor(value);
    if (!normalized) {
        throw new Error(`${context} color is invalid`);
    }
    return normalized;
};

const requireConversationBoolean = (value: JsonValue | undefined, field: string, context: string): boolean => {
    if (!isBoolean(value)) {
        throw new Error(`${context} ${field} is missing or invalid`);
    }
    return value;
};

const requireNonNegativeNumber = (value: JsonValue | undefined, field: string, context: string): number => {
    if (!isNumber(value) || !Number.isInteger(value) || value < 0) {
        throw new Error(`${context} ${field} is missing or invalid`);
    }
    return value;
};

const mergeModelSettingsRecords = (currentValue: JsonObject, patchValue: JsonObject): JsonObject => {
    const merged: JsonObject = { ...currentValue };
    for (const [key, nextValue] of Object.entries(patchValue)) {
        const existingValue = merged[key];
        if (isPlainObject(existingValue) && isPlainObject(nextValue)) {
            merged[key] = mergeModelSettingsRecords(existingValue, nextValue);
            continue;
        }
        merged[key] = nextValue;
    }
    return merged;
};

const mergeModelSettingsPatch = (currentSettings: Conversation['modelSettings'], value: JsonValue | undefined, context: string): Conversation['modelSettings'] => {
    if (!isJsonObject(value)) {
        throw new Error(`${context} model_settings is invalid`);
    }
    const merged = mergeModelSettingsRecords(serializeConversationModelSettings(currentSettings), value);
    return parseConversationModelSettings(merged);
};

export { mergeModelSettingsPatch, parseRequiredModelSettings, requireBackendConversationTitle, requireConversationBoolean, requireConversationColor, requireConversationModelSettings, requireConversationTitle, requireEpochMs, requireNonNegativeNumber };
