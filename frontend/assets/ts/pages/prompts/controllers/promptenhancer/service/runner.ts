/* SoAI - Prompts page runner [frontend/assets/ts/pages/prompts/controllers/promptenhancer/service/runner.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError } from '@core/errors/abort.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
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
    readonly #isCurrent: () => boolean;
    readonly #catalogRequest = new LatestRequestController();
    readonly #waitMessageTimer: TimeoutTimer;

    constructor(options: { host: PromptEnhancerDependencies['host']; resources: PromptEnhancerDependencies['resources']; systemPrompt: string; state: StateAccess; catalog: CatalogAccess; isCurrent: () => boolean; render: () => void }) {
        this.#host = options.host;
        this.#resources = options.resources;
        this.#systemPrompt = options.systemPrompt;
        this.#state = options.state;
        this.#catalog = options.catalog;
        this.#render = options.render;
        this.#isCurrent = options.isCurrent;
        this.#waitMessageTimer = new TimeoutTimer(5000, () => this.#showWaitMessage());

        if (this.#catalog.get().status === 'idle') {
            this.#catalog.set(createInitialPromptEnhancerModelCatalogState());
        }
    }

    async reloadModelCatalog(): Promise<void> {
        if (!this.#isCurrent()) return;
        await this.#catalogRequest.runLatest(async (request) => {
            try {
                const catalog = await this.#host.fetchModelCatalog(request.signal);
                if (request.isStale() || !this.#isCurrent()) return;
                this.#catalog.set(catalog === null ? { status: 'unavailable', availableModelIds: new Set<string>() } : buildPromptEnhancerModelCatalogState(catalog));
            } catch (error) {
                if (request.isStale() || !this.#isCurrent() || isAbortError(error)) return;
                this.#host.feedback.handle(ensureError(error), 'Prompt enhancer model catalog reload failed');
                this.#catalog.set({ status: 'error', availableModelIds: new Set<string>() });
            }
            if (this.#state.get().source) {
                if (this.#state.get().status !== 'streaming') this.#syncModelSelectionToCatalog();
                this.#render();
            }
        });
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
        if (!this.#isCurrent()) return;
        const state = this.#state.get();
        const source = state.source;
        if (!source || state.status === 'streaming' || state.abortController !== null) return;
        const controller = new AbortController();
        state.abortController = controller;
        const isCurrent = (): boolean => this.#isCurrent() && this.#state.get() === state && state.abortController === controller && !controller.signal.aborted;
        try {
            if (this.#catalog.get().status !== 'ready') await this.reloadModelCatalog();
            if (!isCurrent()) return;
            this.#syncModelSelectionToCatalog();
            if (!isCurrent()) return;
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
            this.#startWaitMessageTimer();
            this.#render();
            await this.#stream(state, controller);
        } finally {
            if (state.abortController === controller) state.abortController = null;
        }
    }

    async handleRunOrStop(): Promise<void> {
        if (this.#state.get().status === 'streaming') {
            this.stopStreaming();
            return;
        }
        await this.runEnhancement();
    }

    async #stream(state: PromptEnhancerRunState, controller: AbortController): Promise<void> {
        const source = state.source;
        const isCurrent = (): boolean => this.#isCurrent() && this.#state.get() === state && state.abortController === controller;
        if (!isCurrent() || !source || !state.modelId) {
            return;
        }
        let renderHandle: number | null = null;
        try {
            if (controller.signal.aborted) {
                state.status = 'aborted';
                state.statusMessage = i18n.t('prompts.enhancer.status.aborted');
                state.errorMessage = null;
                return;
            }
            let pendingOutput = '';
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
                    if (!isCurrent() || controller.signal.aborted || state.status !== 'streaming') {
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
                    if (!isCurrent() || controller.signal.aborted) return;
                    pendingOutput += value;
                    scheduleFlush();
                }
            });

            if (!isCurrent()) return;

            if (renderHandle !== null) {
                this.#resources.cancelAnimationFrame(renderHandle);
                renderHandle = null;
            }
            pendingOutput = '';
            state.output = response.output;
            if (controller.signal.aborted || state.status === 'aborted') {
                state.status = 'aborted';
                state.statusMessage = i18n.t('prompts.enhancer.status.aborted');
                state.errorMessage = null;
                return;
            }
            if (!state.output.trim()) {
                state.status = 'error';
                state.statusMessage = i18n.t('prompts.enhancer.status.error');
                state.errorMessage = i18n.t('prompts.enhancer.errors.empty');
                this.#host.feedback.show(state.errorMessage, 'warning');
                return;
            }
            state.status = 'success';
            state.statusMessage = i18n.t('prompts.enhancer.status.complete');
        } catch (error) {
            if (!isCurrent()) return;
            const runtimeError = ensureError(error);
            if (state.status === 'aborted' || isAbortError(runtimeError) || controller.signal.aborted) {
                state.status = 'aborted';
                state.statusMessage = i18n.t('prompts.enhancer.status.aborted');
                state.errorMessage = null;
            } else {
                this.#host.feedback.handle(runtimeError, 'Prompt enhancement failed');
                state.status = 'error';
                state.statusMessage = i18n.t('prompts.enhancer.status.error');
                state.errorMessage = i18n.t('prompts.enhancer.errors.generic');
            }
        } finally {
            if (renderHandle !== null) this.#resources.cancelAnimationFrame(renderHandle);
            if (isCurrent()) {
                this.#hideWaitMessage();
                state.abortController = null;
                this.#render();
            }
        }
    }

    dispose(): void {
        this.#catalogRequest.invalidate();
        this.stopStreaming();
    }

    stopStreaming(): void {
        this.#hideWaitMessage();
        const state = this.#state.get();
        state.status = 'aborted';
        state.statusMessage = i18n.t('prompts.enhancer.status.aborted');
        state.errorMessage = null;
        const controller = state.abortController;
        state.abortController = null;
        controller?.abort();
        this.#render();
    }
}

export { PromptEnhancerRunner };
