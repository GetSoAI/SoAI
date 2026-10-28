/* SoAI - Wizard AI setup step incremental presentation [frontend/assets/ts/pages/wizard/controllers/AiSetupStepUiController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setWizardDisclosureExpanded } from '@pages/wizard/widgets/WizardDisclosureWidget.ts';
import { animatePresenceMorph, measurePresenceSize, stopPresenceAnimation, insertWithPresence, removeWithPresence, isPresenceExiting } from '@core/animations/presence/public.ts';
import { createHtmlFragment } from '@core/dom/html.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { dom } from '@core/dom/dom.ts';
import { scrollElementIntoView } from '@core/scroll.ts';
import { i18n } from '@core/i18n/index.ts';
import { createOperationProgressReporter } from '@core/operationprogress/public.ts';
import type { OperationProgressReporter } from '@core/operationprogress/types.ts';
import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import type { AiSetupWizardStepId } from '@features/wizard/public.ts';
import { applyModelSearchCheckerboard, applyVariantCheckerboard, highlightVariantProbeSelection } from '@features/models/public.ts';
import type { AiSetupConnectView, AiSetupModelsView } from '@pages/wizard/contracts/aisetup/types.ts';
import { AI_ENGINE_INPUT_NAME, AI_ENGINE_MODE_INPUT_NAME, renderCloudRegion, resolveCloudRegionMode } from '@pages/wizard/rendering/aisetup/connect/view.ts';
import { AI_CLOUD_FILTER_ID, cloudSelectionKey, itemSelectionKey, localSelectionKey, renderAiCloudModels, renderAiPickedModels } from '@pages/wizard/rendering/aisetup/models/view.ts';
import { describeAiSetupRow, visibleAiProgressRows, readReadyCountText, renderAiProgressRow, renderAiRowActions } from '@pages/wizard/rendering/aisetup/progress/view.ts';
import { renderAiSearchResults, renderAiSearchVariants } from '@pages/wizard/rendering/aisetup/search/view.ts';
import { renderAiSetupLoadFailedStep } from '@pages/wizard/rendering/aisetup/view.ts';
import type { AiSetupProgressSummary } from '@pages/wizard/services/aisetup/progress/mappers.ts';
import type { ModelSearchState } from '@pages/wizard/services/aisetup/AiSetupModelSearchController.ts';
import type { WizardViewContext } from '@pages/wizard/types.ts';

const CONNECT_PROGRESS_KEY = 'ai-setup-connect';

interface AiSetupStepUiControllerHost {
    createViewContext(): WizardViewContext;
    updateHTML(element: HTMLElement, value: TrustedHtml): void;
    updateText(element: HTMLElement, value: string): void;
    toggleHidden(element: HTMLElement, hidden: boolean): void;
    toggleClassName(element: HTMLElement, className: string, value: boolean): void;
    updateProperty(element: HTMLElement, property: string, value: boolean): void;
    cancelRow(key: string): Promise<void>;
}

const optionalElement = (selector: string, root: ParentNode): HTMLElement | null => {
    const element = dom.resolve(selector, root instanceof Element || root instanceof Document ? root : null);
    return element instanceof HTMLElement ? element : null;
};

const elements = (selector: string, root: HTMLElement): HTMLElement[] => dom.resolveAll(selector, root).filter((element): element is HTMLElement => element instanceof HTMLElement);

class AiSetupStepUiController {
    readonly #host: AiSetupStepUiControllerHost;
    readonly #rowReporters = new Map<string, OperationProgressReporter>();
    #connectReporter: OperationProgressReporter | null = null;
    #content: HTMLElement | null = null;
    #stepId: AiSetupWizardStepId | null = null;
    #renderedSearch: ModelSearchState | null = null;

    constructor(host: AiSetupStepUiControllerHost) {
        this.#host = host;
    }

    attach(stepId: AiSetupWizardStepId, content: HTMLElement): void {
        this.detach();
        this.#stepId = stepId;
        this.#content = content;
    }

    detach(): void {
        for (const reporter of this.#rowReporters.values()) reporter.destroy();
        this.#rowReporters.clear();
        this.#connectReporter?.destroy();
        this.#connectReporter = null;
        this.#content = null;
        this.#stepId = null;
        this.#renderedSearch = null;
    }

    get stepId(): AiSetupWizardStepId | null {
        return this.#stepId;
    }

    syncLoadFailed(): void {
        const content = this.#content;
        const stepId = this.#stepId;
        if (content === null || stepId === null || optionalElement('[data-action="wizard-ai-retry-load"]', content) !== null) return;
        this.attach(stepId, content);
        this.#host.updateHTML(content, toTrustedUiHtml(renderAiSetupLoadFailedStep(this.#host.createViewContext())));
    }

    syncConnect(view: AiSetupConnectView): void {
        const content = this.#content;
        if (content === null) return;
        this.#syncChoice(content, AI_ENGINE_MODE_INPUT_NAME, 'automatic', view.engineMode === 'automatic' && view.automaticLine !== null);
        for (const engine of view.engines) this.#syncChoice(content, AI_ENGINE_INPUT_NAME, engine.pluginName, engine.selected);
        const region = optionalElement('[data-ai-region="cloud"]', content);
        if (region === null) return;
        const mode = resolveCloudRegionMode(view);
        if (region.dataset['aiMode'] !== mode) {
            this.#connectReporter?.destroy();
            this.#connectReporter = null;
            this.#updateRegion(region, toTrustedUiHtml(renderCloudRegion(this.#host.createViewContext(), view)));
            region.dataset['aiMode'] = mode;
        }
        if (mode === 'form') this.#syncProviderForm(region, view);
    }

    syncModels(view: AiSetupModelsView): void {
        const content = this.#content;
        if (content === null) return;
        const selectedKeys = new Map<string, string>();
        for (const card of view.localCards) if (card.itemId !== null) selectedKeys.set(localSelectionKey(card.card.entry.id), card.itemId);
        for (const picked of view.pickedModels) selectedKeys.set(itemSelectionKey(picked.itemId), picked.itemId);
        for (const model of view.cloudModels) if (model.itemId !== null) selectedKeys.set(cloudSelectionKey(model.modelId), model.itemId);
        this.#syncPickedModels(content, view);
        this.#syncCloudModels(content, view);
        for (const wrapper of elements('[data-ai-model]', content)) {
            const key = wrapper.dataset['aiModel'] ?? '';
            const itemId = selectedKeys.get(key) ?? null;
            const choice = optionalElement('.wizard-ai-choice, .wizard-ai-cloud-choice', wrapper);
            const input = choice === null ? null : optionalElement('input', choice);
            if (choice !== null) this.#host.toggleClassName(choice, 'is-selected', itemId !== null);
            if (input instanceof HTMLInputElement) {
                this.#host.updateProperty(input, 'checked', itemId !== null);
                this.#host.updateProperty(input, 'disabled', !key.startsWith('cloud:') && view.localSelectionLocked);
            }
            const openChat = optionalElement('[data-ai-open-chat]', wrapper);
            const radio = openChat === null ? null : optionalElement('input', openChat);
            if (openChat !== null) this.#host.toggleHidden(openChat, !(view.showOpenChat && itemId !== null));
            if (radio instanceof HTMLInputElement) this.#host.updateProperty(radio, 'checked', itemId !== null && itemId === view.firstChatItemId);
        }
        this.#syncSearch(content, view.search);
        const variants = optionalElement('[data-ai-region="search-variants"]', content);
        if (variants !== null) {
            highlightVariantProbeSelection(variants, view.selectedVariantIndex);
            for (const entry of elements('.variant-check-entry', variants)) entry.setAttribute('aria-disabled', String(view.localSelectionLocked));
        }
        this.#syncCloudFilter(content, view.cloudFilter);
    }

    #syncChoice(content: HTMLElement, name: string, value: string, selected: boolean): void {
        const input = optionalElement(`input[name="${name}"][value="${CSS.escape(value)}"]`, content);
        if (!(input instanceof HTMLInputElement)) return;
        this.#host.updateProperty(input, 'checked', selected);
        const card = input.closest('.wizard-choice-card');
        if (card instanceof HTMLElement) this.#host.toggleClassName(card, 'is-selected', selected);
    }

    #syncPickedModels(content: HTMLElement, view: AiSetupModelsView): void {
        const region = optionalElement('[data-ai-region="picked"]', content);
        if (region === null) return;
        const rendered = elements('[data-ai-model]', region).map((wrapper) => wrapper.dataset['aiModel'] ?? '');
        const expected = view.pickedModels.map((picked) => itemSelectionKey(picked.itemId));
        if (rendered.join('\n') !== expected.join('\n')) this.#updateRegion(region, toTrustedUiHtml(renderAiPickedModels(this.#host.createViewContext(), view)));
    }

    #syncCloudModels(content: HTMLElement, view: AiSetupModelsView): void {
        const region = optionalElement('[data-ai-region="cloud-models"]', content);
        if (region === null) return;
        const rendered = elements('.wizard-ai-cloud-model', region).map((wrapper) => wrapper.dataset['aiModel'] ?? '');
        if (rendered.join('\n') === view.cloudModels.map((model) => cloudSelectionKey(model.modelId)).join('\n')) return;
        const filterFocused = optionalElement(`#${AI_CLOUD_FILTER_ID}`, region)?.matches(':focus') === true;
        this.#updateRegion(region, toTrustedUiHtml(renderAiCloudModels(this.#host.createViewContext(), view)));
        const filter = filterFocused ? optionalElement(`#${AI_CLOUD_FILTER_ID}`, region) : null;
        if (filter instanceof HTMLInputElement) filter.focus();
    }

    syncProgress(summary: AiSetupProgressSummary): void {
        const content = this.#content;
        const list = content === null ? null : optionalElement('[data-ai-progress-list]', content);
        if (content === null || list === null) return;
        const context = this.#host.createViewContext();
        const renderedKeys = elements(':scope > .wizard-ai-progress-item[data-ai-row]', list)
            .filter((row) => !isPresenceExiting(row))
            .map((row) => row.dataset['aiRow'] ?? '');
        const rows = visibleAiProgressRows(summary, renderedKeys);
        if (renderedKeys.join('\n') !== rows.map((row) => row.key).join('\n')) {
            const created = document.createElement('div');
            const markup = toTrustedUiHtml(rows.map((row) => renderAiProgressRow(context, row)).join(''));
            created.appendChild(createHtmlFragment({ documentRef: document, html: markup.html, context: list }));
            patchOrderedChildren({
                existingParent: list,
                createdParent: created,
                resolveChildKey: (row) => row.dataset['aiRow'] ?? null,
                patchChild: () => false,
                insertChild: (parent, row, anchor) => {
                    insertWithPresence(parent, row, anchor);
                    return row;
                },
                removeChild: (row) => {
                    const key = row.dataset['aiRow'] ?? '';
                    this.#rowReporters.get(key)?.destroy();
                    this.#rowReporters.delete(key);
                    if (row.contains(dom.getActiveElement())) (optionalElement('button', list) ?? content).focus({ preventScroll: true });
                    removeWithPresence(row);
                },
                isChildDetaching: isPresenceExiting,
                replaceUnsupportedChildren: () => {
                    throw new Error('Wizard progress rows require unique identities');
                }
            });
        }
        for (const row of rows) {
            const item = optionalElement(`:scope > .wizard-ai-progress-item[data-ai-row="${CSS.escape(row.key)}"]`, list);
            if (item === null) continue;
            this.#requireRowReporter(row.key, item).update(row.key, describeAiSetupRow(row));
            const actions = optionalElement('[data-ai-row-actions]', item);
            const signature = row.actions.join(',');
            if (actions !== null && actions.dataset['aiActions'] !== signature) {
                const hadFocus = actions.contains(dom.getActiveElement());
                this.#host.updateHTML(actions, toTrustedUiHtml(renderAiRowActions(context, row)));
                this.#host.toggleHidden(actions, row.actions.length === 0);
                actions.dataset['aiActions'] = signature;
                if (hadFocus) (optionalElement('button', actions) ?? item).focus({ preventScroll: true });
            }
        }
        const readyCount = optionalElement('[data-ai-ready-count]', content);
        const readyText = readReadyCountText(summary);
        if (readyCount !== null && readyCount.textContent !== readyText) this.#host.updateText(readyCount, readyText);
    }

    focusCloudError(): void {
        const error = this.#content === null ? null : optionalElement('[data-ai-cloud-error]:not(.u-hidden)', this.#content);
        if (error === null) return;
        error.setAttribute('tabindex', '-1');
        error.focus({ preventScroll: true });
        scrollElementIntoView(error);
    }

    openModelSearch(): void {
        const content = this.#content;
        if (content === null) return;
        const toggle = optionalElement('[aria-controls="wizard-ai-search"]', content);
        if (toggle !== null) setWizardDisclosureExpanded(toggle, true);
        const input = optionalElement('#wizard-ai-search-input', content);
        if (!(input instanceof HTMLInputElement)) return;
        input.focus({ preventScroll: true });
        scrollElementIntoView(input, { block: 'center' });
    }

    #requireRowReporter(key: string, item: HTMLElement): OperationProgressReporter {
        const existing = this.#rowReporters.get(key);
        if (existing !== undefined) return existing;
        const slot = optionalElement('[data-ai-row-progress]', item) ?? item;
        const reporter = createOperationProgressReporter(slot, { showCancel: true, showBadge: true, onCancel: (rowKey) => this.#host.cancelRow(rowKey) });
        this.#rowReporters.set(key, reporter);
        return reporter;
    }

    #syncProviderForm(region: HTMLElement, view: AiSetupConnectView): void {
        const connecting = view.connection.connecting;
        for (const control of elements('input, select, button[type="submit"]', region)) this.#host.updateProperty(control, 'disabled', connecting);
        const progress = optionalElement('[data-ai-cloud-progress]', region);
        if (progress !== null && connecting) {
            this.#connectReporter ??= createOperationProgressReporter(progress, { showCancel: false, showBadge: false });
            this.#connectReporter.update(CONNECT_PROGRESS_KEY, { message: i18n.t('wizard.aiSetup.connect.cloud.connecting', { name: view.connection.connectingName }), state: 'downloading', indeterminate: true });
        } else if (this.#connectReporter !== null) {
            this.#connectReporter.destroy();
            this.#connectReporter = null;
        }
        const error = optionalElement('[data-ai-cloud-error]', region);
        if (error !== null) {
            this.#host.updateText(error, view.connection.error?.message ?? '');
            this.#host.toggleHidden(error, view.connection.error === null);
        }
    }

    #syncSearch(content: HTMLElement, search: ModelSearchState): void {
        if (this.#renderedSearch === search) return;
        const previous = this.#renderedSearch;
        this.#renderedSearch = search;
        const context = this.#host.createViewContext();
        const results = optionalElement('[data-ai-region="search-results"]', content);
        const variants = optionalElement('[data-ai-region="search-variants"]', content);
        const resultsChanged = previous === null || previous.status !== search.status || previous.results !== search.results || previous.error !== search.error;
        const variantsChanged = previous === null || previous.variantStatus !== search.variantStatus || previous.variants !== search.variants || previous.variantError !== search.variantError;
        let resultsAnimation: Animation | null = null;
        let variantsAnimation: Animation | null = null;
        if (results !== null && resultsChanged) {
            resultsAnimation = this.#updateRegion(results, toTrustedUiHtml(renderAiSearchResults(context, search)));
            applyModelSearchCheckerboard(results);
        }
        if (variants !== null && variantsChanged) {
            variantsAnimation = this.#updateRegion(variants, toTrustedUiHtml(renderAiSearchVariants(context, search)));
            applyVariantCheckerboard(variants);
        }
        dom.flush();
        const target = variantsChanged && search.variantStatus !== 'idle' ? variants : resultsChanged && search.status !== 'idle' ? results : null;
        if (target === null) return;
        const reveal = (): void => {
            if (this.#content === content && this.#renderedSearch === search && target.closest('[inert]') === null) scrollElementIntoView(target, { block: 'start' });
        };
        const animation = target === variants ? variantsAnimation : resultsAnimation;
        if (animation === null) reveal();
        else animation.addEventListener('finish', reveal, { once: true });
    }

    #updateRegion(region: HTMLElement, markup: TrustedHtml): Animation | null {
        const previous = measurePresenceSize(region);
        stopPresenceAnimation(region);
        this.#host.updateHTML(region, markup);
        dom.flush();
        const next = measurePresenceSize(region);
        return next === null ? null : animatePresenceMorph(region, previous ?? { width: next.width, height: 0 }, next, { fadeChildren: false, preserveWrapping: true });
    }

    #syncCloudFilter(content: HTMLElement, filter: string): void {
        const query = filter.trim().toLowerCase();
        let visible = 0;
        for (const row of elements('.wizard-ai-cloud-model', content)) {
            const matches = query === '' || (row.dataset['aiFilterText'] ?? '').includes(query);
            this.#host.toggleHidden(row, !matches);
            if (matches) visible += 1;
        }
        const noMatch = optionalElement('[data-ai-cloud-no-match]', content);
        if (noMatch !== null) this.#host.toggleHidden(noMatch, visible > 0);
    }
}

export { AiSetupStepUiController };
export type { AiSetupStepUiControllerHost };
