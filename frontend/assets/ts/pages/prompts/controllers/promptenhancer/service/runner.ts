/* SoAI - Prompts page runner [frontend/assets/ts/pages/prompts/controllers/promptenhancer/service/runner.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { TimeoutTimer } from '@core/timers/timeoutTimer.ts';
import { buildPromptEnhancerModelCatalogState, createInitialPromptEnhancerModelCatalogState, resolvePromptEnhancerDisabledReason } from '@pages/prompts/controllers/promptenhancer/catalog.ts';
import { runPromptEnhancerStreamingRequest } from '@pages/prompts/controllers/promptenhancer/service/streamingRunner.ts';
import type { PromptEnhancerDependencies, PromptEnhancerModelCatalogState, PromptEnhancerRunState } from '@pages/prompts/controllers/promptenhancer/types.ts';

type StateAccess = {
    get: () => PromptEnhancerRunState;
    set: (state: PromptEnhancerRunState) => void;
};

type CatalogAccess = {
    get: () => PromptEnhancerModelCatalogState;
    set: (catalog: PromptEnhancerModelCatalogState) => void;
};

type ModelSelectionResult = {
    selected: string | null;
    changedFrom: string | null;
};

const getSortedCatalogModelIds = (catalog: PromptEnhancerModelCatalogState): string[] => {
    if (catalog.status !== 'ready') {
        return [];
    }
    return Array.from(catalog.availableModelIds).sort((firstValue, secondValue) => firstValue.localeCompare(secondValue, getCurrentLocale()));
};

const resolvePromptEnhancerModelSelection = (catalog: PromptEnhancerModelCatalogState, currentModelId: string | null): ModelSelectionResult => {
    if (catalog.status !== 'ready') {
        return { selected: currentModelId, changedFrom: null };
    }
    const sorted = getSortedCatalogModelIds(catalog);
    if (sorted.length === 0) {
        return { selected: null, changedFrom: currentModelId };
    }
    if (currentModelId && catalog.availableModelIds.has(currentModelId)) {
        return { selected: currentModelId, changedFrom: null };
    }
    const selected = sorted[0] ?? null;
    if (!selected) {
        return { selected: currentModelId, changedFrom: null };
    }
    return { selected, changedFrom: currentModelId && currentModelId !== selected ? currentModelId : null };
};

class PromptEnhancerRunner {
    readonly #host: PromptEnhancerDependencies['host'];
    readonly #resources: PromptEnhancerDependencies['resources'];
    readonly #systemPrompt: string;
    readonly #state: StateAccess;
    readonly #catalog: CatalogAccess;
    readonly #render: () => void;
    readonly #waitMessageTimer: TimeoutTimer;

    constructor(options: { host: PromptEnhancerDependencies['host']; resources: PromptEnhancerDependencies['resources']; systemPrompt: string; state: StateAccess; catalog: CatalogAccess; render: () => void }) {
        this.#host = options.host;
        this.#resources = options.resources;
        this.#systemPrompt = options.systemPrompt;
        this.#state = options.state;
        this.#catalog = options.catalog;
        this.#render = options.render;
        this.#waitMessageTimer = new TimeoutTimer(5000, () => this.#showWaitMessage());

        if (this.#catalog.get().status === 'idle') {
            this.#catalog.set(createInitialPromptEnhancerModelCatalogState());
        }
    }

    async reloadModelCatalog(): Promise<void> {
        try {
            const catalog = await this.#host.fetchModelCatalog();
            this.#catalog.set(catalog === null ? { status: 'unavailable', availableModelIds: new Set<string>() } : buildPromptEnhancerModelCatalogState(catalog));
        } catch (error) {
            this.#host.feedback.handle(ensureError(error), 'Prompt enhancer model catalog reload failed');
            this.#catalog.set({ status: 'error', availableModelIds: new Set<string>() });
        }
        if (this.#state.get().source) {
            this.#syncModelSelectionToCatalog();
            this.#render();
        }
    }

    syncSelectedModelToCatalog(): void {
        this.#syncModelSelectionToCatalog();
    }

    #showWaitMessage(): void {
        const state = this.#state.get();
        if (state.status !== 'streaming' || state.output.length > 0) {
            return;
        }
        state.showWaitMessage = true;
        this.#render();
    }

    #hideWaitMessage(): void {
        this.#waitMessageTimer.stop();
        const state = this.#state.get();
        state.showWaitMessage = false;
    }

    #startWaitMessageTimer(): void {
        this.#waitMessageTimer.start();
    }

    #syncModelSelectionToCatalog(): void {
        const state = this.#state.get();
        const catalog = this.#catalog.get();
        const current = state.modelId;
        const resolved = resolvePromptEnhancerModelSelection(catalog, current);

        if (resolved.selected === null) {
            state.modelId = null;
            state.modelHelpMessage = i18n.t('prompts.enhancer.modelHelp.noneAvailable');
            return;
        }
        if (resolved.selected === current) {
            return;
        }
        if (resolved.changedFrom) {
            state.modelHelpMessage = i18n.t('prompts.enhancer.modelHelp.selectionChanged', { model: resolved.changedFrom, selected: resolved.selected });
        }
        state.modelId = resolved.selected;
        this.#host.setPromptEnhancerModel(resolved.selected);
    }

    async runEnhancement(): Promise<void> {
        const state = this.#state.get();
        const source = state.source;
        if (!source) {
            return;
        }
        if (state.status === 'streaming') {
            return;
        }
        if (this.#catalog.get().status !== 'ready') {
            await this.reloadModelCatalog();
        }
        this.#syncModelSelectionToCatalog();
        const reason = resolvePromptEnhancerDisabledReason(source.content, state.modelId, this.#catalog.get());
        if (reason) {
            state.errorMessage = reason;
            state.status = 'error';
            state.statusMessage = i18n.t('prompts.enhancer.status.error');
            this.#render();
            return;
        }
        state.output = '';
        state.errorMessage = null;
        state.detectedLanguage = null;
        state.status = 'streaming';
        state.statusMessage = i18n.t('prompts.enhancer.status.streaming');
        state.showWaitMessage = false;
        state.abortController = new AbortController();
        this.#startWaitMessageTimer();
        this.#render();
        await this.#stream();
    }

    async handleRunOrStop(): Promise<void> {
        if (this.#state.get().status === 'streaming') {
            this.stopStreaming();
            return;
        }
        await this.runEnhancement();
    }

    async #stream(): Promise<void> {
        const state = this.#state.get();
        const source = state.source;
        const controller = state.abortController;
        if (!source || !controller || !state.modelId) {
            return;
        }
        try {
            if (controller.signal.aborted) {
                state.status = 'aborted';
                state.statusMessage = i18n.t('prompts.enhancer.status.aborted');
                state.errorMessage = i18n.t('prompts.enhancer.errors.aborted');
                return;
            }
            let pendingOutput = '';
            let renderHandle: number | null = null;
            const flushPendingOutput = (): void => {
                if (!pendingOutput) {
                    return;
                }
                this.#hideWaitMessage();
                state.output += pendingOutput;
                pendingOutput = '';
                this.#render();
            };
            const scheduleFlush = (): void => {
                if (renderHandle !== null) {
                    return;
                }
                renderHandle = this.#resources.requestAnimationFrame(() => {
                    renderHandle = null;
                    if (controller.signal.aborted || state.status !== 'streaming') {
                        return;
                    }
                    flushPendingOutput();
                });
            };

            const response = await runPromptEnhancerStreamingRequest({
                modelId: state.modelId,
                systemPrompt: this.#systemPrompt,
                content: source.content,
                signal: controller.signal,
                onChunk: (value) => {
                    pendingOutput += value;
                    scheduleFlush();
                }
            });

            if (renderHandle !== null) {
                this.#resources.cancelAnimationFrame(renderHandle);
                renderHandle = null;
            }
            pendingOutput = '';
            state.output = response.output;
            if (!state.output.trim()) {
                throw new Error(i18n.t('prompts.enhancer.errors.empty'));
            }
            if (controller.signal.aborted || state.status === 'aborted') {
                state.status = 'aborted';
                state.statusMessage = i18n.t('prompts.enhancer.status.aborted');
                state.errorMessage = i18n.t('prompts.enhancer.errors.aborted');
                return;
            }
            state.status = 'success';
            state.statusMessage = i18n.t('prompts.enhancer.status.complete');
        } catch (error) {
            const runtimeError = ensureError(error);
            if (state.status === 'aborted' || isAbortError(runtimeError) || controller.signal.aborted) {
                state.status = 'aborted';
                state.statusMessage = i18n.t('prompts.enhancer.status.aborted');
                state.errorMessage = i18n.t('prompts.enhancer.errors.aborted');
            } else {
                this.#host.feedback.handle(runtimeError, 'Prompt enhancement failed');
                state.status = 'error';
                state.statusMessage = i18n.t('prompts.enhancer.status.error');
                state.errorMessage = i18n.t('prompts.enhancer.errors.generic');
            }
        } finally {
            this.#hideWaitMessage();
            state.abortController = null;
            this.#render();
        }
    }

    stopStreaming(): void {
        this.#hideWaitMessage();
        const state = this.#state.get();
        state.status = 'aborted';
        state.statusMessage = i18n.t('prompts.enhancer.status.aborted');
        state.errorMessage = i18n.t('prompts.enhancer.errors.aborted');
        state.abortController?.abort();
        state.abortController = null;
        this.#render();
    }
}

export { PromptEnhancerRunner };
