/* SoAI - Prompts picker modal controller [frontend/assets/ts/features/prompts/picker/PromptsPickerModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { checkerboardService } from '@core/dom/dom.ts';
import { resolveDelegatedActionElementResult } from '@core/dom/dataAction.ts';
import { resolveHandledOperationCause } from '@core/operationErrorNotifier.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isThenable } from '@core/typeGuards.ts';
import { PROMPTS_PICKER_MODAL_ID } from '@features/prompts/modals/constants.ts';
import { openPromptContentPreview } from '@features/prompts/promptPreview.ts';
import { normalizePromptRecord, type PromptRecord } from '@features/prompts/promptRecords.ts';
import { PROMPTS_PICKER_ACTION_EDIT, PROMPTS_PICKER_ACTION_INSERT, isPromptsPickerActionId, type PromptsPickerActionId } from '@features/prompts/picker/actions.ts';
import { filterPromptsPickerPrompts, normalizePromptsPickerPayload, upsertPromptsPickerPrompt } from '@features/prompts/picker/mappers.ts';
import { createPromptsPickerPreviewHost } from '@features/prompts/picker/adapters.ts';
import { resolvePromptsPickerRefs } from '@features/prompts/picker/dom.ts';
import { startPromptsPickerStream } from '@features/prompts/picker/service.ts';
import type { PromptsPickerModalHost, PromptsPickerRefs, PromptsPickerState } from '@features/prompts/picker/types.ts';
import { renderPromptsPickerModal } from '@features/prompts/picker/view.ts';

const SEARCH_RENDER_DELAY_MS = 80;

class PromptsPickerModalController implements EventListenerObject {
    readonly #host: PromptsPickerModalHost;
    readonly #timers = new ResourceTracker();
    #abortController: AbortController | null = null;
    #refs: PromptsPickerRefs | null = null;
    #unsubscribePrompts: (() => void) | null = null;
    #renderTimer: number | null = null;
    #session = 0;
    #state: PromptsPickerState = {
        prompts: [],
        query: '',
        loading: false,
        errorMessage: null
    };

    constructor(host: PromptsPickerModalHost) {
        this.#host = host;
    }

    async open(): Promise<void> {
        this.dispose();
        this.#session += 1;
        const session = this.#session;
        const presenter = requireModalPresenter();
        presenter.open(PROMPTS_PICKER_MODAL_ID);
        const root = presenter.requireElement(PROMPTS_PICKER_MODAL_ID);
        const refs = resolvePromptsPickerRefs(root);
        refs.manageButton.hidden = this.#host.openLibrary === null;
        refs.manageButton.disabled = this.#host.openLibrary === null;
        this.#abortController = new AbortController();
        this.#refs = refs;
        this.#state = { prompts: [], query: '', loading: true, errorMessage: null };
        this.#bind(refs);
        this.#renderIfActive();
        await startPromptsPickerStream({
            manager: this.#host.requireStreamManager(),
            signal: this.#requireSignal(),
            session,
            setUnsubscribe: (unsubscribe) => {
                if (this.#isActiveSession(session)) this.#unsubscribePrompts = unsubscribe;
                else unsubscribe();
            },
            isActive: (activeSession) => this.#isActiveSession(activeSession),
            applyPayload: (value) => this.#applyPromptPayload(value),
            handleError: (error, message) => this.#handleError(error, message),
            finishLoading: (activeSession) => this.#finishLoading(activeSession)
        });
    }

    dispose(): void {
        this.#session += 1;
        if (this.#renderTimer !== null) {
            this.#timers.clearTimeout(this.#renderTimer);
            this.#renderTimer = null;
        }
        this.#unsubscribePrompts?.();
        this.#unsubscribePrompts = null;
        if (this.#refs) checkerboardService.disconnect(checkerboardService.getContainerId(this.#refs.results));
        this.#abortController?.abort();
        this.#abortController = null;
        this.#refs = null;
    }

    #bind(refs: PromptsPickerRefs): void {
        const signal = this.#requireSignal();
        refs.root.addEventListener('click', this, { signal });
        refs.root.addEventListener('keydown', this, { signal });
        refs.root.addEventListener('input', this, { signal });
        refs.root.addEventListener('core.modal.close', this, { signal });
    }

    #requireSignal(): AbortSignal {
        if (!this.#abortController) {
            throw new Error('Prompts picker abort controller is not active');
        }
        return this.#abortController.signal;
    }

    handleEvent(event: Event): void {
        const refs = this.#refs;
        if (!refs) {
            throw new Error('Prompts picker refs are not active');
        }
        if (event.type === 'core.modal.close') this.dispose();
        else if (event.type === 'input' && event.target === refs.searchInput) this.#handleSearchInput(refs);
        else if (event.type === 'click' && event.target === refs.searchButton) this.#handleSearchInput(refs);
        else if (event.type === 'click' && event.target === refs.manageButton) {
            event.preventDefault();
            event.stopPropagation();
            this.#handleManage();
        } else if (event.type === 'click') this.#handleClick(refs, event);
        else if (event.type === 'keydown') this.#handleKeydown(event);
    }

    #applyPromptPayload(value: JsonValue): void {
        this.#state.prompts = normalizePromptsPickerPayload(value);
        this.#state.errorMessage = null;
        this.#scheduleRender();
    }

    #finishLoading(session: number): void {
        if (this.#isActiveSession(session)) {
            this.#state.loading = false;
            this.#scheduleRender();
        }
    }

    #upsertPromptRecord<T>(record: T): PromptRecord {
        if (!this.#abortController || this.#abortController.signal.aborted) {
            return normalizePromptRecord(record);
        }
        const result = upsertPromptsPickerPrompt(this.#state.prompts, record);
        this.#state.prompts = result.prompts;
        this.#scheduleRender();
        return result.prompt;
    }

    #handleSearchInput(refs: PromptsPickerRefs): void {
        this.#state.query = refs.searchInput.value.trim();
        this.#scheduleRender(SEARCH_RENDER_DELAY_MS);
    }

    #handleManage(): void {
        if (this.#host.openLibrary === null) return;
        const session = this.#session;
        try {
            const result = this.#host.openLibrary();
            requireModalPresenter().close(PROMPTS_PICKER_MODAL_ID, { restoreFocus: false });
            if (isThenable(result)) {
                Promise.resolve(result).catch((error) => {
                    if (this.#isActiveSession(session)) this.#handleManageError(error);
                });
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            if (this.#isActiveSession(session)) this.#handleManageError(runtimeError);
        }
    }

    #handleManageError(error: Error): void {
        const runtimeError = ensureError(error);
        this.#host.feedback.handle(runtimeError, 'Prompts picker navigation failed');
        if (resolveHandledOperationCause(runtimeError) === null) this.#host.feedback.show(i18n.t('prompts.picker.manageFailed'), 'error');
    }

    #handleClick(refs: PromptsPickerRefs, event: Event): void {
        const actionResult = resolveDelegatedActionElementResult({
            root: refs.root,
            event,
            preventDefault: 'interactive',
            stopPropagation: true,
            mouseButton: 'primary',
            ignoreDisabled: true
        });
        if (actionResult.type !== 'action') {
            return;
        }
        const action = actionResult.actionElement.dataset.action;
        if (!isPromptsPickerActionId(action)) {
            throw new Error(`Prompts picker received unsupported action ${String(action)}`);
        }
        this.#dispatchAction(action, this.#requirePromptId(actionResult.actionElement));
    }

    #handleKeydown(event: Event): void {
        if (!(event instanceof KeyboardEvent) || (event.key !== 'Enter' && event.key !== ' ')) {
            return;
        }
        const target = event.target;
        if (!(target instanceof HTMLElement) || !target.classList.contains('prompts-picker-card')) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        this.#insertPrompt(this.#requirePromptId(target));
    }

    #dispatchAction(action: PromptsPickerActionId, promptId: string): void {
        if (action === PROMPTS_PICKER_ACTION_INSERT) {
            this.#insertPrompt(promptId);
            return;
        }
        if (action === PROMPTS_PICKER_ACTION_EDIT) {
            const session = this.#session;
            void this.#openPromptEditor(promptId).catch((error) => {
                if (this.#isActiveSession(session)) this.#handlePromptEditorError(ensureError(error));
            });
        }
    }

    #requirePromptId(element: HTMLElement): string {
        const promptId = element.dataset['promptId'];
        if (!promptId) {
            throw new Error('Prompts picker action requires a prompt id');
        }
        return promptId;
    }

    #findPrompt(promptId: string | number): PromptRecord | null {
        const normalizedId = String(promptId);
        return this.#state.prompts.find((prompt) => prompt.id === normalizedId) ?? null;
    }

    #insertPrompt(promptId: string): void {
        const prompt = this.#findPrompt(promptId);
        if (!prompt) {
            throw new Error(`Prompts picker could not find prompt ${promptId}`);
        }
        this.#host.onSelect(prompt.content);
        requireModalPresenter().close(PROMPTS_PICKER_MODAL_ID, { restoreFocus: false });
    }

    async #openPromptEditor(promptId: string): Promise<void> {
        const session = this.#session;
        const signal = this.#requireSignal();
        await openPromptContentPreview(
            createPromptsPickerPreviewHost({
                promptsApi: this.#host.promptsApi,
                findPromptById: (id) => (this.#isActiveSession(session) ? this.#findPrompt(id) : null),
                upsertPromptRecord: (record) => (this.#isActiveSession(session) ? this.#upsertPromptRecord(record) : normalizePromptRecord(record)),
                getDocument: () => this.#host.getDocument(),
                showNotification: (message, type, duration) => {
                    if (this.#isActiveSession(session)) this.#host.feedback.show(message, type, duration);
                }
            }),
            promptId,
            { edit: true, signal }
        );
    }

    #handlePromptEditorError(error: Error): void {
        const runtimeError = ensureError(error);
        if (isAbortError(runtimeError)) return;
        this.#host.feedback.handle(runtimeError, 'Prompts picker editor failed');
        if (resolveHandledOperationCause(runtimeError) === null) this.#host.feedback.show(i18n.t('prompts.picker.editFailed'), 'error');
    }

    #scheduleRender(delayMs = 0): void {
        if (this.#renderTimer !== null) {
            this.#timers.clearTimeout(this.#renderTimer);
        }
        const session = this.#session;
        this.#renderTimer = this.#timers.setTimeout(() => {
            if (!this.#isActiveSession(session)) return;
            this.#renderTimer = null;
            this.#renderIfActive();
        }, delayMs);
    }

    #renderIfActive(): void {
        const refs = this.#refs;
        if (!refs || !this.#abortController || this.#abortController.signal.aborted) {
            return;
        }
        renderPromptsPickerModal({
            refs,
            state: this.#state,
            visiblePrompts: filterPromptsPickerPrompts(this.#state.prompts, this.#state.query),
            getEditIcon: () => this.#host.getCachedIcon('rename', { size: 14, strokeWidth: 1 })
        });
    }

    #isActiveSession(session: number): boolean {
        return this.#session === session && Boolean(this.#abortController) && this.#abortController?.signal.aborted === false;
    }

    #handleError(error: Error, message: string): void {
        const runtimeError = ensureError(error);
        if (isAbortError(runtimeError) || !this.#abortController || this.#abortController.signal.aborted) {
            return;
        }
        this.#host.feedback.handle(runtimeError, 'Prompts picker load failed');
        this.#state.loading = false;
        const cause = resolveHandledOperationCause(runtimeError);
        this.#state.errorMessage = cause ?? message;
        if (cause === null) this.#host.feedback.show(this.#state.errorMessage, 'error');
        this.#scheduleRender();
    }
}

export { PromptsPickerModalController };
