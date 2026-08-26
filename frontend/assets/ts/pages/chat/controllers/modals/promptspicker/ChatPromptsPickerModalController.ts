/* SoAI - Chat prompts picker modal controller [frontend/assets/ts/pages/chat/controllers/modals/promptspicker/ChatPromptsPickerModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { checkerboardService } from '@core/dom/dom.ts';
import { resolveDelegatedActionElementResult } from '@core/dom/dataAction.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isThenable } from '@core/typeGuards.ts';
import { CHAT_PROMPTS_PICKER_MODAL_ID } from '@features/chat/public.ts';
import { openPromptContentPreview, type PromptRecord } from '@features/prompts/public.ts';
import { CHAT_PROMPTS_PICKER_ACTION_EDIT, CHAT_PROMPTS_PICKER_ACTION_INSERT, isChatPromptsPickerActionId, type ChatPromptsPickerActionId } from '@pages/chat/controllers/modals/promptspicker/actions.ts';
import { filterChatPromptsPickerPrompts, normalizeChatPromptsPickerPayload, normalizeChatPromptsPickerPrompt, upsertChatPromptsPickerPrompt } from '@pages/chat/controllers/modals/promptspicker/mappers.ts';
import { createChatPromptsPickerPreviewHost } from '@pages/chat/controllers/modals/promptspicker/adapters.ts';
import { resolveChatPromptsPickerRefs } from '@pages/chat/controllers/modals/promptspicker/dom.ts';
import { startChatPromptsPickerStream } from '@pages/chat/controllers/modals/promptspicker/service.ts';
import type { ChatPromptsPickerModalHost, ChatPromptsPickerRefs, ChatPromptsPickerState } from '@pages/chat/controllers/modals/promptspicker/types.ts';
import { renderChatPromptsPickerModal } from '@pages/chat/controllers/modals/promptspicker/view.ts';

const SEARCH_RENDER_DELAY_MS = 80;

class ChatPromptsPickerModalController implements EventListenerObject {
    readonly #host: ChatPromptsPickerModalHost;
    readonly #timers = new ResourceTracker();
    #abortController: AbortController | null = null;
    #refs: ChatPromptsPickerRefs | null = null;
    #unsubscribePrompts: (() => void) | null = null;
    #renderTimer: number | null = null;
    #session = 0;
    #state: ChatPromptsPickerState = {
        prompts: [],
        query: '',
        loading: false,
        errorMessage: null
    };

    constructor(host: ChatPromptsPickerModalHost) {
        this.#host = host;
    }

    async open(): Promise<void> {
        this.dispose();
        this.#session += 1;
        const session = this.#session;
        const presenter = requireModalPresenter();
        presenter.open(CHAT_PROMPTS_PICKER_MODAL_ID);
        const root = presenter.requireElement(CHAT_PROMPTS_PICKER_MODAL_ID);
        const refs = resolveChatPromptsPickerRefs(root);
        this.#abortController = new AbortController();
        this.#refs = refs;
        this.#state = { prompts: [], query: '', loading: true, errorMessage: null };
        this.#bind(refs);
        this.#renderIfActive();
        await startChatPromptsPickerStream({
            manager: this.#host.requireStreamManager(),
            signal: this.#requireSignal(),
            session,
            setUnsubscribe: (unsubscribe) => {
                this.#unsubscribePrompts = unsubscribe;
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

    #bind(refs: ChatPromptsPickerRefs): void {
        const signal = this.#requireSignal();
        refs.root.addEventListener('click', this, { signal });
        refs.root.addEventListener('keydown', this, { signal });
        refs.root.addEventListener('input', this, { signal });
        refs.root.addEventListener('core.modal.close', this, { signal });
    }

    #requireSignal(): AbortSignal {
        if (!this.#abortController) {
            throw new Error('Chat prompts picker abort controller is not active');
        }
        return this.#abortController.signal;
    }

    handleEvent(event: Event): void {
        const refs = this.#refs;
        if (!refs) {
            throw new Error('Chat prompts picker refs are not active');
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
        this.#state.prompts = normalizeChatPromptsPickerPayload(value);
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
            return normalizeChatPromptsPickerPrompt(record);
        }
        const result = upsertChatPromptsPickerPrompt(this.#state.prompts, record);
        this.#state.prompts = result.prompts;
        this.#scheduleRender();
        return result.prompt;
    }

    #handleSearchInput(refs: ChatPromptsPickerRefs): void {
        this.#state.query = refs.searchInput.value.trim();
        this.#scheduleRender(SEARCH_RENDER_DELAY_MS);
    }

    #handleManage(): void {
        try {
            const result = this.#host.navigate('prompts');
            requireModalPresenter().close(CHAT_PROMPTS_PICKER_MODAL_ID, { restoreFocus: false });
            if (isThenable(result)) {
                Promise.resolve(result).catch((error) => this.#handleManageError(error));
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#handleManageError(runtimeError);
        }
    }

    #handleManageError(error: Error): void {
        const runtimeError = ensureError(error);
        this.#host.feedback.handle(runtimeError, 'Prompts picker navigation failed');
        this.#host.feedback.show(i18n.t('chat.promptsPicker.manageFailed'), 'error');
    }

    #handleClick(refs: ChatPromptsPickerRefs, event: Event): void {
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
        if (!isChatPromptsPickerActionId(action)) {
            throw new Error(`Chat prompts picker received unsupported action ${String(action)}`);
        }
        this.#dispatchAction(action, this.#requirePromptId(actionResult.actionElement));
    }

    #handleKeydown(event: Event): void {
        if (!(event instanceof KeyboardEvent) || (event.key !== 'Enter' && event.key !== ' ')) {
            return;
        }
        const target = event.target;
        if (!(target instanceof HTMLElement) || !target.classList.contains('chat-prompts-picker-card')) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        this.#insertPrompt(this.#requirePromptId(target));
    }

    #dispatchAction(action: ChatPromptsPickerActionId, promptId: string): void {
        if (action === CHAT_PROMPTS_PICKER_ACTION_INSERT) {
            this.#insertPrompt(promptId);
            return;
        }
        if (action === CHAT_PROMPTS_PICKER_ACTION_EDIT) {
            void this.#openPromptEditor(promptId).catch((error) => this.#handlePromptEditorError(error));
        }
    }

    #requirePromptId(element: HTMLElement): string {
        const promptId = element.dataset['promptId'];
        if (!promptId) {
            throw new Error('Chat prompts picker action requires a prompt id');
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
            throw new Error(`Chat prompts picker could not find prompt ${promptId}`);
        }
        this.#host.insertPromptContentIntoComposer(prompt.content);
        requireModalPresenter().close(CHAT_PROMPTS_PICKER_MODAL_ID, { restoreFocus: false });
    }

    async #openPromptEditor(promptId: string): Promise<void> {
        await openPromptContentPreview(
            createChatPromptsPickerPreviewHost({
                api: this.#host.api,
                findPromptById: (id) => this.#findPrompt(id),
                upsertPromptRecord: (record) => this.#upsertPromptRecord(record),
                getDocument: () => this.#host.getDocument(),
                showNotification: (message, type, duration) => this.#host.feedback.show(message, type, duration)
            }),
            promptId,
            { edit: true }
        );
    }

    #handlePromptEditorError(error: Error): void {
        const runtimeError = ensureError(error);
        this.#host.feedback.handle(runtimeError, 'Prompts picker editor failed');
        this.#host.feedback.show(i18n.t('chat.promptsPicker.editFailed'), 'error');
    }

    #scheduleRender(delayMs = 0): void {
        if (this.#renderTimer !== null) {
            this.#timers.clearTimeout(this.#renderTimer);
        }
        this.#renderTimer = this.#timers.setTimeout(() => {
            this.#renderTimer = null;
            this.#renderIfActive();
        }, delayMs);
    }

    #renderIfActive(): void {
        const refs = this.#refs;
        if (!refs || !this.#abortController || this.#abortController.signal.aborted) {
            return;
        }
        renderChatPromptsPickerModal({
            refs,
            state: this.#state,
            visiblePrompts: filterChatPromptsPickerPrompts(this.#state.prompts, this.#state.query),
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
        this.#state.errorMessage = message;
        this.#host.feedback.show(this.#state.errorMessage, 'error');
        this.#scheduleRender();
    }
}

export { ChatPromptsPickerModalController };
