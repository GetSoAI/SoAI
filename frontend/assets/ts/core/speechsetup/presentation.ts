/* SoAI - Localized speech setup guidance and actions [frontend/assets/ts/core/speechsetup/presentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { MODELS_ACTION_DOWNLOAD_MODEL } from '@core/models/pageActions.ts';
import { buildSettingsConfigPathDeepLinkQuery } from '@core/settings/configPathDeepLink.ts';
import { EMPTY_UI_HTML, joinUiHtml, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import type { SpeechSetupCandidate, SpeechSetupNoteOptions, SpeechSetupNotePlacement, SpeechSetupReason, SpeechSetupScope, SpeechSetupSnapshot } from '@core/speechsetup/protocols.ts';

const SPEECH_MODEL_SETTING_PATH = 'TOOLS.MCP.READ_VIDEO.WHISPER_MODEL';
const SPEECH_MODEL_SETTINGS_TAB = 'general';

const textToSpeechReasonMessage = (reason: SpeechSetupReason): string => {
    switch (reason) {
        case 'backend_not_installed':
            return i18n.t('speechSetup.errors.textToSpeechBackendNotInstalled');
        case 'plugin_disabled':
            return i18n.t('speechSetup.errors.textToSpeechPluginDisabled');
        case 'model_disabled':
            return i18n.t('speechSetup.errors.textToSpeechModelDisabled');
        default:
            return i18n.t('speechSetup.errors.noTextToSpeechModel');
    }
};

const speechSetupReasonMessage = (reason: SpeechSetupReason, modelLabel = '', scope: SpeechSetupScope = 'media'): string => {
    if (scope === 'synthesis') return textToSpeechReasonMessage(reason);
    switch (reason) {
        case 'no_tts_plugin':
            return i18n.t('speechSetup.errors.noTextToSpeechModel');
        case 'no_stt_plugin':
            return scope === 'voice' ? i18n.t('speechSetup.errors.noVoiceModel') : i18n.t('speechSetup.errors.noPlugin');
        case 'backend_not_installed':
            return i18n.t('speechSetup.errors.backendNotInstalled');
        case 'plugin_disabled':
            return i18n.t('speechSetup.errors.pluginDisabled');
        case 'no_model_installed':
            return scope === 'voice' ? i18n.t('speechSetup.errors.noVoiceModel') : i18n.t('speechSetup.errors.noModel');
        case 'model_disabled':
            return i18n.t('speechSetup.errors.modelDisabled');
        case 'configured_model_missing':
            return i18n.t('speechSetup.errors.configuredModelMissing');
        case 'not_local':
            return i18n.t('speechSetup.errors.notLocal');
        case 'translation_unsupported':
            return i18n.t('speechSetup.errors.translationUnsupported');
        case 'unsupported_option':
            return modelLabel ? i18n.t('speechSetup.errors.unsupportedOption', { model: modelLabel }) : i18n.t('speechSetup.errors.unsupportedOptionSelected');
    }
};

const speechSetupAskAdministratorMessage = (scope: SpeechSetupScope): string => (scope === 'synthesis' ? i18n.t('speechSetup.askAdministratorTextToSpeech') : i18n.t('speechSetup.askAdministrator'));

const buildSpeechModelSettingsRoute = (): string => `#settings?${new URLSearchParams(buildSettingsConfigPathDeepLinkQuery({ tab: SPEECH_MODEL_SETTINGS_TAB, configPath: SPEECH_MODEL_SETTING_PATH })).toString()}`;

const buildSpeechAddModelRoute = (candidates: readonly SpeechSetupCandidate[]): string => {
    const downloadable = candidates.filter((candidate) => candidate.modelsDownloadable);
    const only = downloadable.length === 1 ? downloadable[0] : undefined;
    const query = new URLSearchParams({ action: MODELS_ACTION_DOWNLOAD_MODEL, ...(only === undefined ? {} : { plugin: only.pluginName }) });
    return `#models?${query.toString()}`;
};

const actionLink = (href: string, label: string): TrustedHtml => uiHtml`<a class="ui-button ui-button--sm ui-variant-neutral" href="${uiAttr(href)}" data-modal-localize="text">${label}</a>`;

const candidateActions = (candidate: SpeechSetupCandidate, grantedActions: ReadonlySet<string>): TrustedHtml[] => {
    if (!grantedActions.has('PLUGIN_ADMIN')) return [];
    const actions: TrustedHtml[] = [];
    if (candidate.backendInstallable) actions.push(uiHtml`<a class="ui-button ui-button--sm ui-variant-accent" href="${uiAttr(`#plugins?${new URLSearchParams({ modal: 'speech-backend', plugin: candidate.pluginName }).toString()}`)}">${renderIconSlot(getIconSync('download', { size: 12, strokeWidth: 1.5 }))}<span data-modal-localize="text">${i18n.t('speechSetup.installBackend', { plugin: candidate.displayName })}</span></a>`);
    if (candidate.enableRequired) actions.push(actionLink(`#plugins?${new URLSearchParams({ modal: 'speech-enable', plugin: candidate.pluginName }).toString()}`, i18n.t('speechSetup.enablePlugin', { plugin: candidate.displayName })));
    return actions;
};

const renderStatus = (titled: boolean, message: string, tone: 'neutral' | 'warning' = 'neutral'): TrustedHtml => uiHtml`<p class="speech-setup-note__status${tone === 'warning' ? ' speech-setup-note__status--warning' : ''}" data-modal-localize="text">${titled ? uiHtml`<strong class="speech-setup-note__title" data-modal-localize="text">${i18n.t('speechSetup.notTranscribed')}</strong>` : EMPTY_UI_HTML}${message ? uiHtml`<span data-modal-localize="text">${message}</span>` : EMPTY_UI_HTML}</p>`;

const renderSpeechSetupNote = (snapshot: SpeechSetupSnapshot, grantedActions: ReadonlySet<string>, options: SpeechSetupNoteOptions = {}): TrustedHtml => {
    const persisted = options.persisted === true;
    const titled = persisted && options.placement !== 'composer';
    const canReadSetup = grantedActions.has('PLUGIN_READ') && grantedActions.has('MODEL_READ');
    const scope = options.scope ?? 'media';
    if (options.placement === 'labelled') return persisted && canReadSetup && snapshot.fresh && (options.reason ?? snapshot.reason) === null ? renderStatus(false, i18n.t('speechSetup.addAgain')) : EMPTY_UI_HTML;
    if (!canReadSetup) return scope !== 'media' && options.reason === undefined ? EMPTY_UI_HTML : renderStatus(titled, speechSetupAskAdministratorMessage(scope), 'warning');
    if (!snapshot.fresh && options.reason === undefined) return titled ? renderStatus(true, '') : EMPTY_UI_HTML;
    const reason = options.reason ?? snapshot.reason;
    if (reason === null) return persisted ? renderStatus(titled, i18n.t('speechSetup.addAgain')) : EMPTY_UI_HTML;
    const addModelVisible = options.addModelVisible === true;
    const candidates = snapshot.fresh ? snapshot.candidates : (options.candidates ?? []);
    const actions = candidates.flatMap((candidate) => candidateActions(candidate, grantedActions));
    if (reason !== 'model_disabled' && !addModelVisible && grantedActions.has('MODEL_ADMIN') && candidates.some((candidate) => candidate.modelsDownloadable)) actions.push(actionLink(buildSpeechAddModelRoute(candidates), i18n.t('models.actions.addModel')));
    if (scope === 'media' && options.placement !== 'settings' && grantedActions.has('CONFIG_PATCH') && snapshot.models.length > 0) actions.push(actionLink(buildSpeechModelSettingsRoute(), i18n.t('speechSetup.changeModel')));
    if ((reason === 'no_stt_plugin' || reason === 'no_tts_plugin') && grantedActions.has('PLUGIN_ADMIN')) actions.push(actionLink('#plugins', i18n.t('speechSetup.openPlugins')));
    if (reason === 'model_disabled' && grantedActions.has('MODEL_ADMIN')) actions.push(actionLink('#models', i18n.t('speechSetup.openModels')));
    const message = speechSetupReasonMessage(reason, options.modelLabel ?? '', scope);
    const status = actions.length > 0 || addModelVisible || options.placement === 'settings' ? message : `${message} ${speechSetupAskAdministratorMessage(scope)}`;
    return uiHtml`${renderStatus(titled, status, 'warning')}${actions.length > 0 ? uiHtml`<div class="speech-setup-actions">${joinUiHtml(actions)}</div>` : EMPTY_UI_HTML}`;
};

const renderSpeechSetupPlaceholder = (persisted = false, placement: SpeechSetupNotePlacement = 'inline'): TrustedHtml => {
    const titled = persisted && placement !== 'labelled' && placement !== 'composer';
    return uiHtml`<div class="speech-setup-note${titled ? '' : ' u-hidden'}" data-speech-setup="${uiAttr(persisted ? 'persisted' : 'advisory')}" data-speech-setup-placement="${uiAttr(placement)}" role="status" data-modal-localize="text">${titled ? renderStatus(true, '') : EMPTY_UI_HTML}</div>`;
};

export { buildSpeechAddModelRoute, buildSpeechModelSettingsRoute, renderSpeechSetupNote, renderSpeechSetupPlaceholder, SPEECH_MODEL_SETTING_PATH, SPEECH_MODEL_SETTINGS_TAB, speechSetupAskAdministratorMessage, speechSetupReasonMessage };
