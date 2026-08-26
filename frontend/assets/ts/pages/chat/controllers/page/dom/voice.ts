/* SoAI - Chat page voice [frontend/assets/ts/pages/chat/controllers/page/dom/voice.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { i18n } from '@core/i18n/index.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { resolveOpenAiEndpointModelId } from '@core/models/modelIdentity.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { supportsOpenAIEndpointForModel } from '@core/openai/capabilityChecks.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { CHAT_CONFIGURATION_MODAL_ID, type ChatParameters } from '@features/chat/public.ts';
import type { ChatPageDomHost } from '@pages/chat/controllers/page/dom/contracts.ts';

const isAudioSpeechCapableModel = (model: ModelData): boolean => supportsOpenAIEndpointForModel(model, 'audio_speech');
const isAudioTranscriptionCapableModel = (model: ModelData): boolean => supportsOpenAIEndpointForModel(model, 'audio_transcriptions');

const appendAudioModelOptions = (selectElement: HTMLSelectElement, autoLabel: string, selectedValue: string, modelIds: string[]): void => {
    const document = selectElement.ownerDocument;
    const autoOption = document.createElement('option');
    autoOption.value = 'auto';
    autoOption.textContent = autoLabel;

    const sortedModelIds = [...new Set(modelIds.filter((id) => id.trim()))];
    sortedModelIds.sort((firstValue, secondValue) => firstValue.localeCompare(secondValue, getCurrentLocale()));

    selectElement.replaceChildren();
    selectElement.append(autoOption);
    for (const id of sortedModelIds) {
        const option = document.createElement('option');
        option.value = id;
        option.textContent = id;
        selectElement.append(option);
    }
    if (selectedValue !== 'auto' && !sortedModelIds.includes(selectedValue)) {
        const selectedOption = document.createElement('option');
        selectedOption.value = selectedValue;
        selectedOption.textContent = selectedValue;
        selectElement.append(selectedOption);
    }
    setSelectValueAndSyncDefault(selectElement, selectedValue || 'auto');
};

const updateVoiceAudioModelSelect = (host: Pick<ChatPageDomHost, 'pageDom'>, inputArguments: { selectorToken: string; selectedValue: string | null; autoLabel: string; models: ModelData[]; predicate: (model: ModelData) => boolean; root?: Element }): void => {
    const selectElement = host.pageDom.optionalHTMLElement(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, inputArguments.selectorToken), inputArguments.root);
    if (!(selectElement instanceof HTMLSelectElement)) {
        return;
    }
    const selectedValue = inputArguments.selectedValue && inputArguments.selectedValue.trim() ? inputArguments.selectedValue.trim() : 'auto';
    const modelIds = inputArguments.models
        .filter(inputArguments.predicate)
        .map(resolveOpenAiEndpointModelId)
        .filter((modelId) => modelId.trim());
    appendAudioModelOptions(selectElement, inputArguments.autoLabel, selectedValue, modelIds);
};

const updateVoiceAudioModelOptions = (host: Pick<ChatPageDomHost, 'pageDom'>, models: ModelData[], parameters: ChatParameters, root?: Element): void => {
    const ttsArguments = {
        selectorToken: 'voice-tts-model-select',
        selectedValue: parameters.voiceTtsModel,
        autoLabel: i18n.t('chat.configuration.voice.ttsModelAuto'),
        models,
        predicate: isAudioSpeechCapableModel
    };
    const sttArguments = {
        selectorToken: 'voice-stt-model-select',
        selectedValue: parameters.voiceSttModel,
        autoLabel: i18n.t('chat.configuration.voice.sttModelAuto'),
        models,
        predicate: isAudioTranscriptionCapableModel
    };
    if (root) {
        updateVoiceAudioModelSelect(host, { ...ttsArguments, root });
        updateVoiceAudioModelSelect(host, { ...sttArguments, root });
        return;
    }
    updateVoiceAudioModelSelect(host, ttsArguments);
    updateVoiceAudioModelSelect(host, sttArguments);
};

export { updateVoiceAudioModelOptions };
