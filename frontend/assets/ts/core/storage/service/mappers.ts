/* SoAI - Shared frontend storage service mapping [frontend/assets/ts/core/storage/service/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StorageRuntime } from '@core/storage/service/types.ts';
import type { SortOrderType } from '@core/storage/types.ts';
import type { ChatUiParameters } from '@core/types/chatParameters.ts';
import { isJsonValue, type JsonRecord, type JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isBoolean, isFiniteNumber, isObject, isString } from '@core/typeGuards.ts';
import { CHAT_PARAMETER_WIRE_KEYS, CHAT_STORAGE_BOOLEAN_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';

type StorageState = StorageRuntime['state'];

const normalizeGPUSettings = (value: JsonValue): JsonRecord | null => {
    if (!isObject(value) || isArray(value)) {
        return null;
    }
    const result: JsonRecord = {};
    for (const [gpuId, gpuSetting] of Object.entries(value)) {
        if (!gpuId.trim()) {
            continue;
        }
        if (isJsonValue(gpuSetting)) {
            result[gpuId] = gpuSetting;
        }
    }
    return result;
};

const applyChatParametersPatch = (parameters: ChatUiParameters, parametersRoot: JsonValue): void => {
    if (!isObject(parametersRoot)) {
        return;
    }
    const patch = parametersRoot;
    const textZoom = patch['text_zoom'];
    if (isFiniteNumber(textZoom)) {
        parameters.textZoom = textZoom;
    }
    const voiceTtsModel = patch['voice_tts_model'];
    if (voiceTtsModel === null || voiceTtsModel === undefined || isString(voiceTtsModel)) {
        parameters.voiceTtsModel = voiceTtsModel ?? null;
    }
    const voiceSttModel = patch['voice_stt_model'];
    if (voiceSttModel === null || voiceSttModel === undefined || isString(voiceSttModel)) {
        parameters.voiceSttModel = voiceSttModel ?? null;
    }
    const voiceTtsVoice = patch['voice_tts_voice'];
    if (voiceTtsVoice === null || voiceTtsVoice === undefined || isString(voiceTtsVoice)) {
        parameters.voiceTtsVoice = voiceTtsVoice ?? null;
    }
    const voiceTtsSpeed = patch['voice_tts_speed'];
    if (voiceTtsSpeed === null || voiceTtsSpeed === undefined || isFiniteNumber(voiceTtsSpeed)) {
        parameters.voiceTtsSpeed = voiceTtsSpeed ?? null;
    }
    for (const parameterKey of CHAT_STORAGE_BOOLEAN_PARAMETER_KEYS) {
        const wireKey = CHAT_PARAMETER_WIRE_KEYS[parameterKey] ?? parameterKey;
        const value = patch[wireKey] ?? null;
        if (isBoolean(value)) {
            parameters[parameterKey] = value;
        }
    }
};

const applyChatPreferencesPatch = (state: StorageState, patch: JsonValue): void => {
    if (!isObject(patch)) {
        return;
    }

    const preferences = state.cache.chat.preferences;
    const hideRealModel = patch['hide_real_model'];
    if (isBoolean(hideRealModel)) {
        preferences.hideRealModel = hideRealModel;
    }
    const userSystemPromptLockEnabled = patch['user_system_prompt_lock_enabled'];
    if (isBoolean(userSystemPromptLockEnabled)) {
        preferences.userSystemPromptLockEnabled = userSystemPromptLockEnabled;
    }
    const userSystemPromptLockValue = patch['user_system_prompt_lock_value'];
    if (userSystemPromptLockValue === null) {
        preferences.userSystemPromptLockValue = null;
    } else if (isString(userSystemPromptLockValue)) {
        const trimmed = userSystemPromptLockValue.trim();
        preferences.userSystemPromptLockValue = trimmed ? trimmed : null;
    }

    const parametersRoot = patch['parameters'];
    applyChatParametersPatch(preferences.parameters, parametersRoot ?? null);
};

const applyHardwarePreferencesPatch = (state: StorageState, patch: JsonValue): void => {
    if (!isObject(patch)) {
        return;
    }
    const hardware = state.cache.hardware;
    const refreshInterval = patch['refresh_interval'];
    if (isFiniteNumber(refreshInterval)) {
        hardware.refreshInterval = refreshInterval;
    }
    const showGraphs = patch['show_graphs'];
    if (isBoolean(showGraphs)) {
        hardware.showGraphs = showGraphs;
    }
    const graphTimeRange = patch['graph_time_range'];
    if (isFiniteNumber(graphTimeRange)) {
        hardware.graphTimeRange = graphTimeRange;
    }
    const gpuSettings = normalizeGPUSettings(patch['gpu_settings'] ?? null);
    if (gpuSettings !== null) {
        hardware.gpuSettings = { ...hardware.gpuSettings, ...gpuSettings };
    }
};

const isSupportedSortOrder = (value: JsonValue): value is SortOrderType => value === 'asc' || value === 'desc';

const collectList = (source: JsonValue, fallback: string[] = []): string[] => {
    if (isArray(source)) {
        return source.map((entry) => (isString(entry) ? entry.trim() : '')).filter(Boolean);
    }
    return [...fallback];
};

export { applyChatParametersPatch, applyChatPreferencesPatch, applyHardwarePreferencesPatch, collectList, isSupportedSortOrder };
