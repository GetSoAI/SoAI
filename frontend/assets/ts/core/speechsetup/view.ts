/* SoAI - Scoped live speech setup guidance [frontend/assets/ts/core/speechsetup/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { loadWebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import { dom } from '@core/dom/dom.ts';
import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireSpeechSetup } from '@core/speechsetup/service.ts';
import { buildSpeechAddModelRoute, renderSpeechSetupNote } from '@core/speechsetup/presentation.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { readSpeechSetupFailure } from '@core/speechsetup/failure.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { isAutoSpeechModelSelector, isSpeechSetupResolved, renderSpeechModelOptions, speechModelMatchesSelector } from '@core/speechsetup/modelSelector.ts';
import type { SpeechSetupNoteOptions, SpeechSetupNotePlacement, SpeechSetupScope } from '@core/speechsetup/protocols.ts';
import { resolveModelDisplayName, resolveOpenAiEndpointModelId } from '@core/models/modelIdentity.ts';
import type { ModelData } from '@core/types/modelTypes.ts';

const SPEECH_SETUP_REFRESH_EVENT = 'speech-setup-refresh';

const readSpeechSetupScope = (value: string | null | undefined): SpeechSetupScope => (value === 'voice' || value === 'synthesis' ? value : 'media');

const speechModelAutoLabel = (scope: SpeechSetupScope, availability: 'checking' | 'empty' | 'available'): string => {
    if (availability === 'checking') return scope === 'synthesis' ? i18n.t('speechSetup.checkingTextToSpeech') : i18n.t('speechSetup.checking');
    if (availability === 'empty') return i18n.t('common.notAvailable');
    return scope === 'synthesis' ? i18n.t('chat.configuration.voice.ttsModelAuto') : i18n.t('chat.configuration.voice.sttModelAuto');
};

const readSpeechSetupNotePlacement = (value: string | undefined): SpeechSetupNotePlacement => (value === 'settings' || value === 'labelled' || value === 'composer' ? value : 'inline');

const resolveSpeechModelLabel = (models: readonly ModelData[], reference: string): string => {
    const model = reference ? models.find((candidate) => reference === (candidate.universalId || candidate.id) || reference === resolveOpenAiEndpointModelId(candidate)) : undefined;
    return model === undefined ? '' : resolveModelDisplayName(model);
};

const mountSpeechSetup = (root: Element, signal: AbortSignal): (() => void) => {
    const getHosts = (): HTMLElement[] => {
        const hosts = dom.resolveAll('[data-speech-setup]', root).filter((host): host is HTMLElement => host instanceof HTMLElement);
        if (root instanceof HTMLElement && root.hasAttribute('data-speech-setup')) hosts.push(root);
        return hosts;
    };
    if (getHosts().length === 0 || signal.aborted) return (): void => {};
    const service = requireSpeechSetup();
    const userId = getAuthManager().getCurrentUser()?.id;
    let grantedActions: ReadonlySet<string> | null = null;
    const render = (): void => {
        if (signal.aborted || getAuthManager().getCurrentUser()?.id !== userId || grantedActions === null) return;
        const snapshot = service.snapshot();
        const modelSelect = dom.resolve('[data-speech-model-select]', root);
        const selected = modelSelect instanceof HTMLSelectElement ? modelSelect.value : null;
        if (modelSelect instanceof HTMLSelectElement && snapshot.fresh) {
            const options = renderSpeechModelOptions(modelSelect.value, snapshot.models);
            if (modelSelect.dataset['speechModelOptions'] !== options.html) {
                replaceChildrenFromTrustedHtml({ element: modelSelect, html: options, context: modelSelect });
                modelSelect.dataset['speechModelOptions'] = options.html;
            }
        }
        const canReadSetup = grantedActions.has('PLUGIN_READ') && grantedActions.has('MODEL_READ');
        const addModelByScope = new Map<SpeechSetupScope, boolean>();
        for (const control of dom.resolveAll('[data-speech-model-control]', root)) {
            const scope = readSpeechSetupScope(control.getAttribute('data-speech-model-control'));
            const controlSnapshot = scope === 'media' ? snapshot : service.snapshot(scope);
            const empty = controlSnapshot.fresh && controlSnapshot.models.length === 0;
            const offerAdd = empty && grantedActions.has('MODEL_ADMIN') && controlSnapshot.candidates.some((candidate) => candidate.modelsDownloadable);
            addModelByScope.set(scope, (addModelByScope.get(scope) ?? false) || offerAdd);
            dom.toggleClass(dom.resolve('.dropdown-select', control), 'u-hidden', offerAdd);
            const addModel = dom.resolve('[data-speech-add-model]', control);
            dom.toggleClass(addModel, 'u-hidden', !offerAdd);
            if (addModel instanceof HTMLAnchorElement && controlSnapshot.fresh) addModel.setAttribute('href', buildSpeechAddModelRoute(controlSnapshot.candidates));
            const autoOption = dom.resolve('option[data-speech-auto-option], option[value="auto"]', control);
            if (autoOption !== null) autoOption.textContent = speechModelAutoLabel(scope, !canReadSetup ? 'available' : !controlSnapshot.fresh ? 'checking' : empty ? 'empty' : 'available');
        }
        for (const host of getHosts()) {
            const error = host.dataset['speechSetupError'];
            const scope = readSpeechSetupScope(host.dataset['speechSetup']);
            const hostSnapshot = scope === 'media' ? snapshot : service.snapshot(scope);
            const failure = error === undefined ? null : readSpeechSetupFailure(parseRequiredJsonText(error));
            const selectedMissing = scope === 'media' && selected !== null && !isAutoSpeechModelSelector(selected) && snapshot.fresh && snapshot.models.length > 0 && !snapshot.models.some((model) => speechModelMatchesSelector(model, selected));
            const resolved = failure !== null && isSpeechSetupResolved(hostSnapshot, failure.reason, failure.selector);
            const shared: SpeechSetupNoteOptions = { scope, addModelVisible: addModelByScope.get(scope) ?? false, placement: readSpeechSetupNotePlacement(host.dataset['speechSetupPlacement']) };
            const options: SpeechSetupNoteOptions = failure === null || resolved ? { ...shared, persisted: host.dataset['speechSetup'] === 'persisted', ...(selectedMissing ? { reason: 'configured_model_missing', selector: selected ?? '' } : {}) } : { ...shared, reason: failure.reason, selector: failure.selector, modelLabel: resolveSpeechModelLabel(hostSnapshot.models, failure.model), candidates: failure.candidates };
            const html = renderSpeechSetupNote(hostSnapshot, grantedActions, options);
            if (host.dataset['speechSetupMarkup'] === html.html) continue;
            host.dataset['speechSetupMarkup'] = html.html;
            replaceChildrenFromTrustedHtml({ element: host, html, context: host });
            dom.toggleClass(host, 'u-hidden', html.html.length === 0);
        }
    };
    const unsubscribe = service.subscribe(render);
    root.addEventListener('change', render, { signal });
    root.addEventListener(SPEECH_SETUP_REFRESH_EVENT, render, { signal });
    signal.addEventListener('abort', unsubscribe, { once: true });
    render();
    const initialize = async (): Promise<void> => {
        const permissions = await loadWebuiPermissionsSnapshot({ signal });
        if (signal.aborted || getAuthManager().getCurrentUser()?.id !== userId) return;
        grantedActions = permissions.grantedActions;
        if (grantedActions.has('PLUGIN_READ') && grantedActions.has('MODEL_READ')) await service.ensureReady();
        render();
    };
    void initialize().catch((error) => {
        if (signal.aborted || isLifecycleCancellationError(error)) return;
        errorHandler.warn('SpeechSetup', 'Speech setup status could not be loaded', ensureError(error));
    });
    return render;
};

export { mountSpeechSetup, SPEECH_SETUP_REFRESH_EVENT };
