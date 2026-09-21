/* SoAI - Chat preset parameter-section snapshot and merge ownership [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatPresetParameterSectionsDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import { CHAT_PARAMETER_WIRE_KEYS, CHAT_WIRE_TO_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import type { ChatParameters } from '@core/chat/parameters/types.ts';
import type { ChatPresetSections } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import { serializeChatPresetSections } from '@core/api/contracts/webuiChatPresetSectionContracts.ts';
import { isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type ParameterPresetSectionId = 'general' | 'appearance' | 'completion' | 'voice';
type ChatParameterKey = Extract<keyof ChatParameters, string>;

const PARAMETER_SECTION_KEYS: Readonly<Record<ParameterPresetSectionId, ReadonlyArray<ChatParameterKey>>> = Object.freeze({
    general: Object.freeze(['hideRealModel', 'conversationPdfExportEnabled', 'newConversationInheritLastSettings', 'ctrlEnterSendEnabled']),
    appearance: Object.freeze(['textZoom', 'widescreenMode', 'richTextEnabled', 'inlineMultimediaPreviewsEnabled', 'autoTitleGeneration', 'showActivities', 'showActivityElapsedTime', 'hideAutomationRuns', 'hideMessagingConversations', 'notifyOnCompletion', 'notifyOnError', 'microphoneSoundEffectsEnabled', 'inputActionVoiceEnabled', 'inputActionCallEnabled', 'inputActionFileUploadEnabled', 'inputActionCameraEnabled', 'inputActionPromptsEnabled', 'inputActionTokenCounterEnabled', 'inputActionNewConversationEnabled', 'inputActionCharacterMapEnabled', 'inputActionMobileAuxiliaryAction']),
    completion: Object.freeze(['contextWindowTokens', 'reasoningEffort', 'reasoningEffortSendEnabled', 'maxCompletionTokens', 'maxCompletionTokensSendEnabled', 'agentMaxIterations', 'temperature', 'topP', 'topPSendEnabled', 'frequencyPenalty', 'frequencyPenaltySendEnabled', 'presencePenalty', 'presencePenaltySendEnabled', 'stop', 'stopSendEnabled', 'topLogprobs', 'logprobsSendEnabled', 'serviceTier']),
    voice: Object.freeze(['voiceTtsModel', 'voiceSttModel'])
});

const cloneParameterValue = (value: JsonValue): JsonValue => (Array.isArray(value) ? [...value] : value);

const wireKeyForParameter = (key: ChatParameterKey): string => CHAT_PARAMETER_WIRE_KEYS[key] ?? key;

const normalizeVoiceValue = (value: JsonValue | undefined): string => (typeof value === 'string' && value.trim() ? value.trim() : 'auto');

const snapshotParameterSection = (parameters: ChatParameters, sectionId: ParameterPresetSectionId, include: (key: ChatParameterKey) => boolean = () => true): JsonObject => {
    const section: JsonObject = {};
    for (const key of PARAMETER_SECTION_KEYS[sectionId]) {
        if (!include(key)) continue;
        const rawValue = sectionId === 'voice' ? normalizeVoiceValue(parameters[key]) : parameters[key];
        if (isJsonValue(rawValue)) {
            section[wireKeyForParameter(key)] = cloneParameterValue(rawValue);
        }
    }
    const canonical = serializeChatPresetSections({ [sectionId]: section });
    const result = canonical[sectionId];
    if (!isJsonObject(result)) {
        throw new Error(`Chat preset ${sectionId} parameter snapshot is empty.`);
    }
    return { ...result };
};

const mergeParameterPresetSection = (parameters: ChatParameters, sectionId: ParameterPresetSectionId, section: JsonObject): ChatParameters => {
    const allowedKeys = new Set<string>(PARAMETER_SECTION_KEYS[sectionId]);
    const next = cloneChatParameters(parameters);
    for (const [wireKey, value] of Object.entries(section)) {
        const parameterKey = CHAT_WIRE_TO_PARAMETER_KEYS[wireKey] ?? wireKey;
        if (!allowedKeys.has(parameterKey)) {
            continue;
        }
        next[parameterKey] = cloneParameterValue(value);
    }
    snapshotParameterSection(next, sectionId);
    return next;
};

const snapshotParameterSections = (parameters: ChatParameters, selectedSections: ReadonlySet<string>, include: (key: ChatParameterKey) => boolean = () => true): ChatPresetSections => {
    const sections: ChatPresetSections = {};
    const sectionIds: readonly ParameterPresetSectionId[] = ['general', 'appearance', 'completion', 'voice'];
    for (const sectionId of sectionIds) {
        if (selectedSections.has(sectionId) && PARAMETER_SECTION_KEYS[sectionId].some(include)) {
            sections[sectionId] = snapshotParameterSection(parameters, sectionId, include);
        }
    }
    return sections;
};

export { mergeParameterPresetSection, PARAMETER_SECTION_KEYS, snapshotParameterSection, snapshotParameterSections };
export type { ParameterPresetSectionId };
