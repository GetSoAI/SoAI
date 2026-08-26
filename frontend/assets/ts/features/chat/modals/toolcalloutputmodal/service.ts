/* SoAI - Tool call output modal service [frontend/assets/ts/features/chat/modals/toolcalloutputmodal/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { ToolCallLiveEventsPage } from '@core/api/contracts/chatRealtimeSnapshotContracts.ts';
import { dom } from '@core/dom/dom.ts';
import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { toTrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { isJsonArray, isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { CHAT_TOOL_CALL_OUTPUT_MODAL_ID } from '@features/chat/modals/constants.ts';
import { replaceCopyButton, resolveToolCallOutputModalContentElements } from '@features/chat/modals/toolcalloutputmodal/dom.ts';
import { renderToolCallOutputModalContent } from '@features/chat/modals/toolcalloutputmodal/view.ts';
import type { ToolCallOutputModalDependencies, ToolCallOutputModalToolCall } from '@features/chat/modals/toolcalloutputmodal/types.ts';

const mergeLiveEventsPage = (toolCall: ToolCallOutputModalToolCall, nextPage: ToolCallLiveEventsPage): void => {
    const currentPage = toolCall['liveEventsPage'];
    if (!isJsonObject(currentPage)) {
        toolCall['liveEventsPage'] = nextPage;
        return;
    }
    const currentEvents = currentPage['events'];
    if (!isJsonArray(currentEvents)) {
        throw new Error(i18n.t('chat.toolCallOutputModal.invalidLiveHistory'));
    }
    const currentPageRecord: JsonObject = currentPage;
    toolCall['liveEventsPage'] = {
        ...currentPageRecord,
        events: [...currentEvents, ...nextPage.events],
        nextBeforeLiveSequence: nextPage.nextBeforeLiveSequence
    };
};

let activeToolOutputSessionGeneration = 0;
let releaseActiveToolOutputSession: (() => void) | null = null;

class ChatToolCallOutputModal {
    readonly #dependencies: ToolCallOutputModalDependencies;
    #copyText: string = '';
    #toolCall: ToolCallOutputModalToolCall | null = null;
    #nextBeforeLiveSequence: number | null = null;
    #loadingMoreLiveHistory: boolean = false;
    #sessionGeneration: number = 0;
    #closedByUser: boolean = true;
    readonly #handleLoadMoreClick = (): void => {
        terminateHandledPromise(this.#loadMoreLiveHistory());
    };

    constructor(dependencies: ToolCallOutputModalDependencies) {
        this.#dependencies = dependencies;
    }

    showLoading(): void {
        const presenter = requireModalPresenter();
        const modalRoot = presenter.requireElement(CHAT_TOOL_CALL_OUTPUT_MODAL_ID);
        this.#activateSession(modalRoot);
        try {
            presenter.open(CHAT_TOOL_CALL_OUTPUT_MODAL_ID);
        } catch (error) {
            this.#deactivateSession();
            throw error;
        }
        const { contentElement, copyButton } = resolveToolCallOutputModalContentElements(CHAT_TOOL_CALL_OUTPUT_MODAL_ID);
        replaceChildrenFromTrustedHtml({
            element: contentElement,
            html: uiHtml`
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <span>${i18n.t('chat.toolCallOutputModal.loading')}</span>
                </div>
            `,
            context: contentElement
        });
        const rebound = replaceCopyButton(copyButton);
        rebound.disabled = true;
        this.#copyText = '';
        this.#toolCall = null;
        this.#nextBeforeLiveSequence = null;
    }

    showError(message: string): void {
        if (!this.#canUpdateModal()) {
            return;
        }
        const { contentElement, copyButton } = resolveToolCallOutputModalContentElements(CHAT_TOOL_CALL_OUTPUT_MODAL_ID);
        const paragraph = contentElement.ownerDocument.createElement('p');
        paragraph.textContent = message;
        contentElement.replaceChildren(paragraph);
        const rebound = replaceCopyButton(copyButton);
        rebound.disabled = true;
        this.#copyText = '';
        this.#toolCall = null;
        this.#nextBeforeLiveSequence = null;
    }

    showToolCall(toolCall: ToolCallOutputModalToolCall): void {
        if (!this.#canUpdateModal()) {
            return;
        }
        this.#toolCall = toolCall;
        this.#renderToolCall(toolCall);
    }

    #activateSession(modalRoot: HTMLElement): void {
        releaseActiveToolOutputSession?.();
        activeToolOutputSessionGeneration += 1;
        const sessionGeneration = activeToolOutputSessionGeneration;
        const closeController = new AbortController();
        const releaseSession = (): void => {
            closeController.abort();
        };
        const handleClose = (): void => {
            this.#deactivateSession();
        };
        releaseActiveToolOutputSession = releaseSession;
        this.#sessionGeneration = sessionGeneration;
        this.#closedByUser = false;
        modalRoot.addEventListener('core.modal.close', handleClose, { signal: closeController.signal });
    }

    #deactivateSession(): void {
        if (activeToolOutputSessionGeneration === this.#sessionGeneration) {
            activeToolOutputSessionGeneration += 1;
            releaseActiveToolOutputSession?.();
            releaseActiveToolOutputSession = null;
        }
        this.#closedByUser = true;
    }

    #canUpdateModal(): boolean {
        if (this.#closedByUser || activeToolOutputSessionGeneration !== this.#sessionGeneration) {
            return false;
        }
        return requireModalPresenter().isOpen(CHAT_TOOL_CALL_OUTPUT_MODAL_ID);
    }

    #renderToolCall(toolCall: ToolCallOutputModalToolCall): void {
        if (!this.#canUpdateModal()) {
            return;
        }
        const { contentElement, copyButton } = resolveToolCallOutputModalContentElements(CHAT_TOOL_CALL_OUTPUT_MODAL_ID);
        const rendered = renderToolCallOutputModalContent(this.#dependencies, toolCall);
        replaceChildrenFromTrustedHtml({
            element: contentElement,
            html: toTrustedHtml(rendered.html),
            context: contentElement
        });
        this.#copyText = rendered.copyText;
        this.#nextBeforeLiveSequence = rendered.nextBeforeLiveSequence;
        const rebound = replaceCopyButton(copyButton);
        rebound.disabled = false;
        const handleCopyClick = (): void => {
            void copyTextWithHostClipboardFeedback(
                {
                    copyToClipboard: (text, options) => this.#dependencies.copyToClipboard(text, options),
                    hasClipboardSupport: () => this.#dependencies.hasClipboardSupport(),
                    showNotification: (message, type): void => this.#dependencies.showNotification(message, type)
                },
                {
                    text: this.#copyText,
                    successMessage: i18n.t('chat.message.copied'),
                    errorMessage: i18n.t('chat.toolCallOutputModal.copyFailed'),
                    unavailableMessage: i18n.t('chat.toolCallOutputModal.copyFailed'),
                    unavailableType: 'error'
                }
            ).catch((error) => {
                const runtimeError = ensureError(error);
                errorHandler.warn('ChatToolCallOutputModal', 'Copy failed', runtimeError);
            });
        };
        rebound.addEventListener('click', handleCopyClick);
        const loadMoreButton = dom.resolve('[data-action="tool-call-live-history-load-more"]', contentElement);
        if (loadMoreButton instanceof HTMLButtonElement) {
            loadMoreButton.disabled = this.#loadingMoreLiveHistory;
            loadMoreButton.addEventListener('click', this.#handleLoadMoreClick);
        }
    }

    async #loadMoreLiveHistory(): Promise<void> {
        const toolCall = this.#toolCall;
        const beforeLiveSequence = this.#nextBeforeLiveSequence;
        const sessionGeneration = this.#sessionGeneration;
        if (toolCall === null || beforeLiveSequence === null || this.#loadingMoreLiveHistory || !this.#canUpdateModal()) {
            return;
        }
        this.#loadingMoreLiveHistory = true;
        try {
            this.#renderToolCall(toolCall);
            await this.#dependencies.runWithBoundary('chat.toolCallOutputModal.loadMoreLiveHistory', async () => {
                const page = await this.#dependencies.loadMoreLiveEvents(beforeLiveSequence);
                if (activeToolOutputSessionGeneration !== sessionGeneration || !this.#canUpdateModal()) {
                    return;
                }
                mergeLiveEventsPage(toolCall, page);
            });
            this.#renderToolCall(toolCall);
        } catch (error) {
            const normalizedError = ensureError(error);
            errorHandler.error('ChatToolCallOutputModal', 'Failed to load additional tool call history', normalizedError);
            if (activeToolOutputSessionGeneration === sessionGeneration && this.#canUpdateModal()) {
                this.#dependencies.showNotification(i18n.t('chat.toolCallOutputModal.failed'), 'error');
            }
        } finally {
            this.#loadingMoreLiveHistory = false;
            if (activeToolOutputSessionGeneration === sessionGeneration) {
                this.#renderToolCall(toolCall);
            }
        }
    }
}

export { ChatToolCallOutputModal };
export type { ToolCallOutputModalDependencies };
