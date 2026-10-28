/* SoAI - Local speech model setting control [frontend/assets/ts/core/speechsetup/modelSelector.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { joinUiHtml, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { MODELS_ACTION_DOWNLOAD_MODEL } from '@core/models/pageActions.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { resolveModelDisplayName, resolveOpenAiEndpointModelId } from '@core/models/modelIdentity.ts';
import { supportsOpenAIEndpointForModel } from '@core/openai/capabilityChecks.ts';
import type { SpeechSetupReason, SpeechSetupScope, SpeechSetupSnapshot } from '@core/speechsetup/protocols.ts';

const isAutoSpeechModelSelector = (selector: string): boolean => !selector.trim() || selector.trim().toLowerCase() === 'auto';

const speechModelMatchesSelector = (model: ModelData, savedSelector: string): boolean => {
    const selector = savedSelector.trim();
    if (isAutoSpeechModelSelector(selector)) return true;
    if (selector === (model.universalId || model.id) || selector === resolveOpenAiEndpointModelId(model)) return true;
    if (!['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3'].includes(selector) || model.family?.toLowerCase() !== 'whisper') return false;
    const identity = selector === 'large' ? 'large-v3' : selector;
    return model.sourceModelId === identity || model.whisperModelId === identity;
};

const isSpeechSetupResolved = (snapshot: SpeechSetupSnapshot, reason: SpeechSetupReason, selector: string): boolean => snapshot.fresh && reason !== 'unsupported_option' && snapshot.models.some((model) => speechModelMatchesSelector(model, selector || 'auto') && (reason !== 'translation_unsupported' || supportsOpenAIEndpointForModel(model, 'audio_translations')));

const renderSpeechModelOptions = (savedValue: string, models: readonly ModelData[]): TrustedHtml => {
    const choices = models
        .map((model) => ({ value: model.universalId || model.id || '', label: resolveModelDisplayName(model) }))
        .filter((entry) => entry.value.length > 0)
        .sort((first, second) => (first.value < second.value ? -1 : first.value > second.value ? 1 : 0));
    const selected = savedValue || 'auto';
    const autoSelected = isAutoSpeechModelSelector(selected);
    const options = [uiHtml`<option data-speech-auto-option value="${uiAttr(autoSelected ? selected : 'auto')}"${autoSelected ? uiHtml` selected` : uiHtml``} data-modal-localize="text">${models.length === 0 ? i18n.t('common.notAvailable') : i18n.t('chat.configuration.voice.sttModelAuto')}</option>`];
    for (const choice of choices) options.push(uiHtml`<option value="${uiAttr(choice.value)}"${selected === choice.value ? uiHtml` selected` : uiHtml``} data-modal-localize="text">${choice.label}</option>`);
    if (!autoSelected && !choices.some((choice) => choice.value === selected)) options.push(uiHtml`<option value="${uiAttr(selected)}" selected>${selected}${models.some((model) => speechModelMatchesSelector(model, selected)) ? '' : ` (${i18n.t('common.notAvailable')})`}</option>`);
    return joinUiHtml(options);
};

const renderSpeechModelControl = (selectMarkup: string, scope: SpeechSetupScope): string => {
    const select = toTrustedUiHtml(renderStandardDropdownSelectControl(selectMarkup));
    return uiHtml`<span class="speech-model-control" data-speech-model-control="${uiAttr(scope)}" data-presence-morph>${select}<a class="ui-button ui-variant-accent u-hidden" data-speech-add-model data-presence href="${uiAttr(`#models?action=${MODELS_ACTION_DOWNLOAD_MODEL}`)}">${getIconSync('add', { size: 24, strokeWidth: 1.5 })}<span data-modal-localize="text">${i18n.t('models.actions.addModel')}</span></a></span>`.html;
};

const renderSpeechModelSelector = (id: string, path: string, savedValue: string, models: readonly ModelData[]): string => renderSpeechModelControl(uiHtml`<select id="${uiAttr(id)}" class="setting-input setting-input--wide" data-path="${uiAttr(path)}" data-speech-model-select>${renderSpeechModelOptions(savedValue, models)}</select>`.html, 'media');

export { isAutoSpeechModelSelector, isSpeechSetupResolved, renderSpeechModelControl, renderSpeechModelOptions, renderSpeechModelSelector, speechModelMatchesSelector };
