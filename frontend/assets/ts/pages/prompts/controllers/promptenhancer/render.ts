/* SoAI - Prompts page render [frontend/assets/ts/pages/prompts/controllers/promptenhancer/render.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { setStatusSurface } from '@core/ui/statusSurface.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { resolvePromptEnhancerDisabledReason } from '@pages/prompts/controllers/promptenhancer/catalog.ts';
import type { PromptEnhancerHost, PromptEnhancerModelCatalogState, PromptEnhancerRunState } from '@pages/prompts/controllers/promptenhancer/types.ts';

const setButtonState = (host: PromptEnhancerHost, modalRoot: HTMLElement, selector: string, enabled: boolean, title: string | null = null): void => {
    const candidate = host.pageDom.requireHTMLElement(selector, modalRoot);
    if (!(candidate instanceof HTMLButtonElement)) {
        throw new TypeError(`Prompt enhancer button '${selector}' is missing`);
    }
    candidate.disabled = !enabled;
    setTooltipText(candidate, title || '');
};

const renderRunButton = (host: PromptEnhancerHost, modalRoot: HTMLElement, state: PromptEnhancerRunState, enabledWhenIdle: boolean): void => {
    const modalId = modalRoot.id;
    const candidate = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'run'), modalRoot);
    if (!(candidate instanceof HTMLButtonElement)) {
        throw new TypeError('Prompt enhancer run button is missing');
    }
    const isStreaming = state.status === 'streaming';
    candidate.textContent = isStreaming ? i18n.t('prompts.enhancer.actions.stop') : i18n.t('prompts.enhancer.actions.run');
    candidate.classList.toggle('ui-variant-danger', isStreaming);
    candidate.classList.toggle('ui-variant-warning', false);
    candidate.classList.toggle('ui-variant-violet', !isStreaming);
    candidate.classList.toggle('ui-variant-primary', false);
    candidate.disabled = !(isStreaming || enabledWhenIdle);
    setTooltipText(candidate, '');
};

const updateStatusBadge = (host: PromptEnhancerHost, modalRoot: HTMLElement, state: PromptEnhancerRunState): void => {
    const modalId = modalRoot.id;
    const badge = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'status-badge'), modalRoot);
    const led = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'status-led'), modalRoot);
    const classes = ['success', 'error', 'warning', 'neutral'];
    classes.forEach((className) => badge.classList.remove(className));
    const ledColors = ['green', 'red', 'orange', 'grey'];
    ledColors.forEach((className) => led.classList.remove(className));

    const { status } = state;
    if (status === 'success') {
        badge.classList.add('success');
        led.classList.add('green');
        return;
    }
    if (status === 'error') {
        badge.classList.add('error');
        led.classList.add('red');
        return;
    }
    if (status === 'streaming') {
        badge.classList.add('warning');
        led.classList.add('orange');
        return;
    }
    badge.classList.add('neutral');
    led.classList.add(status === 'aborted' ? 'orange' : 'grey');
};

const renderModelSelect = (host: PromptEnhancerHost, modalRoot: HTMLElement, state: PromptEnhancerRunState, catalog: PromptEnhancerModelCatalogState): void => {
    const modalId = modalRoot.id;
    const selectCandidate = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'model-select'), modalRoot);
    if (!(selectCandidate instanceof HTMLSelectElement)) {
        throw new TypeError('Prompt enhancer model select must be an HTMLSelectElement');
    }
    const select = selectCandidate;
    select.textContent = '';

    const addOption = (value: string, label: string, disabled: boolean = false): void => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        option.disabled = disabled;
        select.append(option);
    };

    if (catalog.status === 'idle') {
        addOption('', i18n.t('common.loading'), true);
        select.disabled = true;
        return;
    }
    if (catalog.status === 'error') {
        addOption('', i18n.t('prompts.enhancer.modelHelp.catalogErrorOption'), true);
        select.disabled = true;
        return;
    }
    if (catalog.status === 'unavailable') {
        addOption('', i18n.t('prompts.enhancer.modelHelp.unavailableAccessOption'), true);
        select.disabled = true;
        return;
    }
    const sorted = Array.from(catalog.availableModelIds).sort((firstValue, secondValue) => firstValue.localeCompare(secondValue, getCurrentLocale()));
    if (sorted.length === 0) {
        addOption('', i18n.t('prompts.enhancer.modelHelp.noneAvailableOption'), true);
        select.disabled = true;
        return;
    }
    const isStreaming = state.status === 'streaming';
    for (const modelId of sorted) {
        addOption(modelId, modelId);
    }
    select.disabled = isStreaming;
    const value = state.modelId && catalog.availableModelIds.has(state.modelId) ? state.modelId : (sorted[0] ?? '');
    select.value = value;
};

const renderPromptEnhancerOutput = (host: PromptEnhancerHost, modalRoot: HTMLElement, state: PromptEnhancerRunState, _syntaxHighlighter: { detectLanguage(content: string): string; highlight(content: string, language: string): DocumentFragment | Node | string }): void => {
    const modalId = modalRoot.id;
    const output = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'output'), modalRoot);
    const spinner = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'output-spinner'), modalRoot);
    const waitMessage = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'wait-message'), modalRoot);
    const showSpinner = state.status === 'streaming' && state.output.length === 0;
    spinner.classList.toggle('u-hidden', !showSpinner);
    spinner.setAttribute('aria-hidden', showSpinner ? 'false' : 'true');
    waitMessage.classList.toggle('u-hidden', !state.showWaitMessage);
    output.classList.toggle('u-hidden', showSpinner);

    output.textContent = '';
    output.classList.remove('prompt-enhancer-output--plain');
    if (!state.output) {
        if (state.status === 'idle') {
            const hint = i18n.t('prompts.enhancer.outputHint');
            const action = i18n.t('prompts.enhancer.actions.run');
            const index = hint.indexOf(action);
            if (index === -1) {
                output.textContent = hint;
            } else {
                const before = hint.slice(0, index);
                const after = hint.slice(index + action.length);
                if (before.length) {
                    output.append(document.createTextNode(before));
                }
                const actionNode = document.createElement('span');
                actionNode.className = 'prompt-enhancer-output-hint-action';
                actionNode.textContent = action;
                output.append(actionNode);
                if (after.length) {
                    output.append(document.createTextNode(after));
                }
            }
        } else {
            output.textContent = '';
        }
        return;
    }
    output.textContent = state.output;
    output.classList.add('prompt-enhancer-output--plain');
};

const renderPromptEnhancerState = (host: PromptEnhancerHost, modalRoot: HTMLElement, state: PromptEnhancerRunState, catalog: PromptEnhancerModelCatalogState, syntaxHighlighter: { detectLanguage(content: string): string; highlight(content: string, language: string): DocumentFragment | Node | string }): void => {
    const modalId = modalRoot.id;
    const status = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'status-value'), modalRoot);
    const error = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'error'), modalRoot);
    status.textContent = state.statusMessage;
    setStatusSurface({
        surface: error,
        message: state.errorMessage || null
    });

    const doneLed = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'enhanced-done-led'), modalRoot);
    const isStreaming = state.status === 'streaming';
    const isDone = state.status === 'success';
    const ledVisible = isStreaming || isDone;
    doneLed.classList.toggle('u-hidden', !ledVisible);
    doneLed.setAttribute('aria-hidden', ledVisible ? 'false' : 'true');
    doneLed.classList.toggle('prompt-enhancer-done-led--streaming', isStreaming);

    updateStatusBadge(host, modalRoot, state);
    renderModelSelect(host, modalRoot, state, catalog);
    const modelHelp = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'model-help'), modalRoot);
    setStatusSurface({
        surface: modelHelp,
        message: state.modelHelpMessage || null
    });

    const originalPane = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'original-pane'), modalRoot);
    const original = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'original'), modalRoot);
    original.textContent = state.source?.content || '';
    const showOriginal = state.showOriginal;
    originalPane.classList.toggle('u-hidden', !showOriginal);
    originalPane.setAttribute('aria-hidden', showOriginal ? 'false' : 'true');

    const originalCharCount = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'original-char-count'), modalRoot);
    const originalCount = state.source?.content.length ?? 0;
    originalCharCount.textContent = originalCount > 0 ? i18n.t('prompts.enhancer.panes.charCount', { count: i18n.formatNumber(originalCount) }) : '';
    originalCharCount.classList.toggle('u-hidden', originalCount === 0);

    const enhancedCharCount = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'enhanced-char-count'), modalRoot);
    const enhancedCount = state.output.length;
    enhancedCharCount.textContent = enhancedCount > 0 ? i18n.t('prompts.enhancer.panes.charCount', { count: i18n.formatNumber(enhancedCount) }) : '';
    enhancedCharCount.classList.toggle('u-hidden', enhancedCount === 0);

    const panes = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'panes'), modalRoot);
    panes.classList.toggle('prompt-enhancer-panes--split', state.compareSideBySide);

    renderPromptEnhancerOutput(host, modalRoot, state, syntaxHighlighter);
    const hasOutput = state.output.length > 0;
    const canSave = state.status === 'success' && hasOutput;
    const canRun = (() => {
        if (state.status === 'streaming') {
            return false;
        }
        if (!state.source) {
            return false;
        }
        return resolvePromptEnhancerDisabledReason(state.source.content, state.modelId, catalog) === null;
    })();
    renderRunButton(host, modalRoot, state, canRun);
    setButtonState(host, modalRoot, modalUiSelector(modalId, 'copy'), canSave);
    const copyButton = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'copy'), modalRoot);
    copyButton.classList.toggle('u-hidden', !canSave);
    const saveButton = host.pageDom.requireHTMLElement(modalUiSelector(modalId, 'save-new'), modalRoot);
    saveButton.classList.toggle('u-hidden', !canSave);
};

export { renderPromptEnhancerState };
