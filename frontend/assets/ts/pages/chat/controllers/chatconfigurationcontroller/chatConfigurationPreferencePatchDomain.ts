/* SoAI - Chat configuration preference patch ownership [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatConfigurationPreferencePatchDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_PARAMETER_WIRE_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import type { ChatParameters } from '@features/chat/public.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { areParameterValuesEqual } from '@pages/chat/controllers/chatconfigurationcontroller/configurationChangeTracking.ts';

type ChatParameterKey = Extract<keyof ChatParameters, string>;

const SERIALIZED_CONFIGURATION_PREFERENCE_PARAMETER_KEYS = Object.freeze(['conversationPdfExportEnabled', 'newConversationInheritLastSettings', 'richTextEnabled', 'inlineMultimediaPreviewsEnabled', 'autoTitleGeneration', 'showActivities', 'hideAutomationRuns', 'hideMessagingConversations', 'notifyOnCompletion', 'notifyOnError', 'microphoneSoundEffectsEnabled', 'inputActionVoiceEnabled', 'inputActionCallEnabled', 'inputActionFileUploadEnabled', 'inputActionCameraEnabled', 'inputActionPromptsEnabled', 'inputActionTokenCounterEnabled', 'inputActionCharacterMapEnabled', 'inputActionMobileAuxiliaryAction', 'voiceTtsModel', 'voiceSttModel'] satisfies readonly ChatParameterKey[]);

const CONFIGURATION_PREFERENCE_PARAMETER_KEYS = Object.freeze(['hideRealModel', 'textZoom', 'widescreenMode', ...SERIALIZED_CONFIGURATION_PREFERENCE_PARAMETER_KEYS] satisfies readonly ChatParameterKey[]);

const haveConfigurationPreferenceChanges = (current: ChatParameters | null, baseline: ChatParameters | null): boolean => {
    if (!current || !baseline) return false;
    return CONFIGURATION_PREFERENCE_PARAMETER_KEYS.some((key) => !areParameterValuesEqual(key, current[key], baseline[key]));
};

const clonePreferenceValue = (value: JsonValue): JsonValue => (Array.isArray(value) ? [...value] : value);

const buildChatConfigurationPreferencePatch = (parameters: ChatParameters, baseline: ChatParameters, textZoom: number, promptLock: Readonly<{ current: Readonly<{ enabled: boolean; value: string | null }>; baseline: Readonly<{ enabled: boolean; value: string | null }> }>): JsonObject => {
    const parameterPatch: JsonObject = {};
    for (const key of SERIALIZED_CONFIGURATION_PREFERENCE_PARAMETER_KEYS) {
        const value = parameters[key];
        if (!areParameterValuesEqual(key, value, baseline[key]) && value !== undefined && (value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' || Array.isArray(value))) {
            parameterPatch[CHAT_PARAMETER_WIRE_KEYS[key] ?? key] = clonePreferenceValue(value);
        }
    }
    const preferences: JsonObject = {};
    if (Object.keys(parameterPatch).length > 0) preferences['parameters'] = parameterPatch;
    if (!areParameterValuesEqual('hideRealModel', parameters.hideRealModel, baseline.hideRealModel)) preferences['hide_real_model'] = parameters.hideRealModel === true;
    if (promptLock.current.enabled !== promptLock.baseline.enabled || promptLock.current.value !== promptLock.baseline.value) {
        preferences['user_system_prompt_lock_enabled'] = promptLock.current.enabled;
        preferences['user_system_prompt_lock_value'] = promptLock.current.value;
    }
    const chat: JsonObject = {};
    if (Object.keys(preferences).length > 0) chat['preferences'] = preferences;
    if (!areParameterValuesEqual('textZoom', textZoom, baseline.textZoom)) chat['text_zoom'] = textZoom;
    if (!areParameterValuesEqual('widescreenMode', parameters.widescreenMode, baseline.widescreenMode)) chat['widescreen_mode'] = parameters.widescreenMode === true;
    return Object.keys(chat).length > 0 ? { chat } : {};
};

export { buildChatConfigurationPreferencePatch, CONFIGURATION_PREFERENCE_PARAMETER_KEYS, haveConfigurationPreferenceChanges };
