/* SoAI - Prompt enhancer controller ownership [frontend/assets/ts/pages/prompts/controllers/promptenhancer/service/PromptEnhancerController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { drainCleanupStack } from '@core/lifecycle/cleanup.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL, type SaveController } from '@core/save/public.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { isPromptRecord, PROMPTS_ENHANCER_MODAL_ID, type PromptRecord } from '@features/prompts/public.ts';
import { createInitialPromptEnhancerModelCatalogState } from '@pages/prompts/controllers/promptenhancer/catalog.ts';
import { renderPromptEnhancerState } from '@pages/prompts/controllers/promptenhancer/render.ts';
import { PromptEnhancerRunner } from '@pages/prompts/controllers/promptenhancer/service/runner.ts';
import { PROMPT_ENHANCER_SYSTEM_PROMPT } from '@pages/prompts/controllers/promptenhancer/service/constants.ts';
import type { PromptEnhancerDependencies, PromptEnhancerModelCatalogState, PromptEnhancerRunState, PromptEnhancerSourceSnapshot } from '@pages/prompts/controllers/promptenhancer/types.ts';

class PromptEnhancerController {
    private readonly host: PromptEnhancerDependencies['host'];
    private readonly syntaxHighlighter: PromptEnhancerDependencies['syntaxHighlighter'];
    private readonly resources: PromptEnhancerDependencies['resources'];
    private readonly disposers: Array<() => void> = [];
    private readonly promptCreatedListeners = new Set<(promptId: string) => void>();
    private readonly runner: PromptEnhancerRunner;
    private readonly save: SaveController;
    private catalog: PromptEnhancerModelCatalogState = createInitialPromptEnhancerModelCatalogState();
    private state: PromptEnhancerRunState = {
        source: null,
        modelId: null,
        status: 'idle',
        output: '',
        statusMessage: i18n.t('prompts.enhancer.status.idle'),
        errorMessage: null,
        detectedLanguage: null,
        abortController: null,
        showWaitMessage: false,
        showOriginal: true,
        compareSideBySide: true,
        modelHelpMessage: null
    };

    constructor({ host, syntaxHighlighter, resources }: PromptEnhancerDependencies) {
        this.host = host;
        this.syntaxHighlighter = syntaxHighlighter;
        this.resources = resources;
        this.runner = new PromptEnhancerRunner({
            host,
            resources,
            systemPrompt: PROMPT_ENHANCER_SYSTEM_PROMPT,
            state: { get: () => this.state, set: (state) => (this.state = state) },
            catalog: { get: () => this.catalog, set: (catalog) => (this.catalog = catalog) },
            render: () => this.#renderState()
        });
        this.save = createSaveController({
            headerContextId: 'prompt-enhancer',
            headerPriority: SAVE_HEADER_PRIORITY_MODAL,
            requestContextLabel: 'Prompt enhancer save',
            units: [
                {
                    id: 'prompt-enhancer.save-as-new',
                    hasChanges: () => this.#isEnhancerModalOpen() && this.#canSaveAsNew(),
                    save: async () => this.#saveAsNew()
                }
            ]
        });
    }

    setupEventListeners(): void {
        this.disposeListeners();
        const bind = (modalRoot: HTMLElement, selector: string, handler: () => void | Promise<void>): void => {
            const element = this.host.pageDom.requireHTMLElement(selector, modalRoot);
            this.disposers.push(
                this.host.pageResources.on(element, 'click', (event: Event) => {
                    event.preventDefault();
                    void (async (): Promise<void> => {
                        await handler();
                    })().catch((error) => {
                        this.host.feedback.handle(ensureError(error), 'Prompt enhancer action dispatch');
                    });
                })
            );
        };
        const enhancerModalRoot = this.host.modals.requireElement(PROMPTS_ENHANCER_MODAL_ID);
        bind(enhancerModalRoot, modalUiSelector(PROMPTS_ENHANCER_MODAL_ID, 'run'), () => this.handleRunOrStop());
        bind(enhancerModalRoot, modalUiSelector(PROMPTS_ENHANCER_MODAL_ID, 'copy'), () => this.copyOutput());
        bind(enhancerModalRoot, modalUiSelector(PROMPTS_ENHANCER_MODAL_ID, 'save-new'), () => this.save.requestSave());
        bind(enhancerModalRoot, modalUiSelector(PROMPTS_ENHANCER_MODAL_ID, 'close'), () => this.closeEnhancerModal());

        this.disposers.push(this.host.pageResources.on(enhancerModalRoot, 'core.modal.close', () => this.closeModal()));
        const saveButtonCandidate = this.host.pageDom.requireHTMLElement(modalUiSelector(PROMPTS_ENHANCER_MODAL_ID, 'save-new'), enhancerModalRoot);
        if (!(saveButtonCandidate instanceof HTMLButtonElement)) {
            throw new TypeError('Prompt enhancer save button must be an HTMLButtonElement');
        }
        setAriaBusy(enhancerModalRoot, false);
        this.save.attach({
            resolveSaveButtons: () => [saveButtonCandidate],
            busyRoots: [enhancerModalRoot],
            autoNotifyRoot: enhancerModalRoot
        });
        const modelSelectCandidate = this.host.pageDom.requireHTMLElement(modalUiSelector(PROMPTS_ENHANCER_MODAL_ID, 'model-select'), enhancerModalRoot);
        if (!(modelSelectCandidate instanceof HTMLSelectElement)) {
            throw new TypeError('Prompt enhancer model select must be an HTMLSelectElement');
        }
        this.disposers.push(
            this.host.pageResources.on(modelSelectCandidate, 'change', (event: Event) => {
                const target = event.target;
                if (!(target instanceof HTMLSelectElement)) {
                    return;
                }
                if (this.state.status === 'streaming') {
                    return;
                }
                const value = readTrimmedSelectValue(target);
                const selected = value ? value : null;
                this.host.setPromptEnhancerModel(selected);
                this.state.modelId = selected;
                this.state.modelHelpMessage = null;
                this.#renderState();
            })
        );
    }

    async reloadModelCatalog(): Promise<void> {
        await this.runner.reloadModelCatalog();
    }

    closeModal(): void {
        this.runner.stopStreaming();
        delete this.host.modals.requireElement(PROMPTS_ENHANCER_MODAL_ID).dataset['promptColor'];
        this.#resetState();
    }

    dispose(): void {
        this.runner.stopStreaming();
        this.disposeListeners();
        this.#resetState();
        this.save.dispose();
        this.promptCreatedListeners.clear();
    }

    onPromptCreated(listener: (promptId: string) => void): () => void {
        this.promptCreatedListeners.add(listener);
        return () => this.promptCreatedListeners.delete(listener);
    }

    private disposeListeners(): void {
        drainCleanupStack(this.disposers, (runtimeError) => {
            this.host.feedback.handle(runtimeError, 'Prompt enhancer listener cleanup');
        });
    }

    #createSnapshot(prompt: PromptRecord): PromptEnhancerSourceSnapshot {
        return { id: prompt.id, name: prompt.name, content: prompt.content, color: prompt.color, modifiedAtMs: prompt.modifiedAtMs };
    }

    #resetState(): void {
        this.state = {
            source: null,
            modelId: null,
            status: 'idle',
            output: '',
            statusMessage: i18n.t('prompts.enhancer.status.idle'),
            errorMessage: null,
            detectedLanguage: null,
            abortController: null,
            showWaitMessage: false,
            showOriginal: true,
            compareSideBySide: true,
            modelHelpMessage: null
        };
        this.save.notifyChanged();
    }

    #renderState(): void {
        const modalRoot = this.host.modals.requireElement(PROMPTS_ENHANCER_MODAL_ID);
        renderPromptEnhancerState(this.host, modalRoot, this.state, this.catalog, this.syntaxHighlighter);
        this.save.notifyChanged();
    }

    async openFromPrompt(promptId: string | number): Promise<void> {
        const prompt = this.host.findPromptById(promptId);
        if (!isPromptRecord(prompt)) {
            this.host.feedback.show(i18n.t('prompts.enhancer.disabled.noPrompt'), 'warning');
            return;
        }
        if (!toTrimmedString(prompt.content)) {
            this.host.feedback.show(i18n.t('prompts.enhancer.disabled.empty'), 'warning');
            return;
        }
        const promptName = prompt.name || i18n.t('prompts.untitled');
        this.state = {
            source: this.#createSnapshot(prompt),
            modelId: this.host.getPromptEnhancerModel(),
            status: 'idle',
            output: '',
            statusMessage: i18n.t('prompts.enhancer.status.idle'),
            errorMessage: null,
            detectedLanguage: null,
            abortController: null,
            showWaitMessage: false,
            showOriginal: true,
            compareSideBySide: true,
            modelHelpMessage: null
        };
        const modalRoot = this.host.modals.requireElement(PROMPTS_ENHANCER_MODAL_ID);
        const title = this.host.pageDom.requireHTMLElement(modalUiSelector(PROMPTS_ENHANCER_MODAL_ID, 'title'), modalRoot);
        title.textContent = `${i18n.t('prompts.enhancer.title')}: ${promptName}`;
        if (this.catalog.status === 'ready') {
            this.runner.syncSelectedModelToCatalog();
        } else if (this.catalog.status === 'idle' || this.catalog.status === 'unavailable') {
            terminateHandledPromise(this.reloadModelCatalog());
        }
        this.host.closePromptView();
        this.host.modals.open(PROMPTS_ENHANCER_MODAL_ID);
        const animationFrameReady = createDeferred<void>();
        this.resources.requestAnimationFrame((): void => {
            animationFrameReady.resolve();
        });
        await animationFrameReady.promise;
        this.#renderState();
    }

    async runEnhancement(): Promise<void> {
        await this.runner.runEnhancement();
    }

    async handleRunOrStop(): Promise<void> {
        await this.runner.handleRunOrStop();
    }

    async copyOutput(): Promise<void> {
        await this.host.copyPromptContent(this.state.output || null);
    }

    async #saveAsNew(): Promise<void> {
        const source = this.state.source;
        if (!source || !this.#canSaveAsNew()) {
            return;
        }
        const created = await this.host.runTask(
            'prompts.enhancer.saveNew',
            () =>
                this.host.createPrompt({
                    name: i18n.t('prompts.enhancer.newName', { name: source.name }),
                    content: this.state.output,
                    color: source.color
                }),
            { displayName: i18n.t('prompts.enhancer.actions.saveAsNew'), rethrow: false }
        );
        if (!created) {
            return;
        }
        const saved = this.host.upsertPromptRecord(created);
        this.host.feedback.show(i18n.t('prompts.enhancer.notifications.savedNew'), 'success');
        this.closeEnhancerModal();
        const promptId = saved.id ?? source.id;
        for (const listener of this.promptCreatedListeners) listener(promptId);
    }

    closeEnhancerModal(): void {
        this.host.modals.close(PROMPTS_ENHANCER_MODAL_ID);
    }

    #isEnhancerModalOpen(): boolean {
        return this.host.modals.isOpen(PROMPTS_ENHANCER_MODAL_ID);
    }

    #canSaveAsNew(): boolean {
        return this.state.status === 'success' && toTrimmedString(this.state.output).length > 0 && !!this.state.source;
    }
}

export { PROMPT_ENHANCER_SYSTEM_PROMPT, PromptEnhancerController };
