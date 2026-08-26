/* SoAI - Chat attachment overflow modal content view [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { createKnowledgeToolbar, renderAttachmentOverflowTabs, type AttachmentOverflowTabCounts } from '@features/chat/message/attachmentoverflowmodal/controls.ts';
import type { AttachmentOverflowCategoryFilter, KnowledgeStatusFilter } from '@features/chat/message/attachmentoverflowmodal/filters.ts';

type AttachmentOverflowModalViewState = {
    activeTab: AttachmentOverflowCategoryFilter;
    tabCounts: AttachmentOverflowTabCounts;
    knowledgeActive: boolean;
    statusFilter: KnowledgeStatusFilter;
    query: string;
    errorMessage: string | null;
    loadingKnowledge: boolean;
    hasNextKnowledgePage: boolean;
    recordsCount: number;
};

const LIST_CLASS_NAME = 'chat-attachment-overflow-list';
const EMPTY_CLASS_NAME = 'chat-attachment-overflow-empty';
const TOOLBAR_CLASS_NAME = 'chat-attachment-overflow-toolbar';

const resolveEmptyText = (state: AttachmentOverflowModalViewState): string => {
    if (state.recordsCount > 0 || state.loadingKnowledge) {
        return '';
    }
    if (state.knowledgeActive && (state.query || state.statusFilter !== 'all')) {
        return i18n.t('chat.attachments.modal.emptySearch');
    }
    if (state.activeTab === 'attachment') {
        return i18n.t('chat.attachments.modal.emptyAttachments');
    }
    if (state.activeTab === 'soaiLink') {
        return i18n.t('chat.attachments.modal.emptySoaiLinks');
    }
    if (state.activeTab === 'knowledge') {
        return i18n.t('chat.attachments.modal.emptyKnowledge');
    }
    return i18n.t('chat.attachments.modal.emptyAll');
};

class AttachmentOverflowModalShell {
    readonly list: HTMLElement;
    readonly empty: HTMLElement;
    readonly scrollRoot: HTMLElement;
    readonly sentinel: HTMLElement;
    readonly #tabsHost: HTMLElement;
    readonly #toolbar: HTMLElement;
    readonly #error: HTMLElement;
    readonly #errorText: HTMLElement;
    readonly #loading: HTMLElement;

    constructor(content: HTMLElement, tabsHost: HTMLElement) {
        this.scrollRoot = content;
        this.#tabsHost = tabsHost;
        this.#toolbar = dom.getDocument().createElement('div');
        this.#error = dom.getDocument().createElement('div');
        this.#errorText = dom.getDocument().createElement('span');
        this.list = dom.getDocument().createElement('div');
        this.empty = dom.getDocument().createElement('div');
        this.#loading = dom.getDocument().createElement('div');
        this.sentinel = dom.getDocument().createElement('div');
        this.#configureError();
        this.#configureListNodes();
        this.#configureLoading();
        content.replaceChildren(this.#toolbar, this.#error, this.list, this.empty, this.#loading, this.sentinel);
    }

    update(state: AttachmentOverflowModalViewState): void {
        renderAttachmentOverflowTabs(this.#tabsHost, {
            activeTab: state.activeTab,
            counts: state.tabCounts
        });
        this.#updateToolbar(state);
        this.#updateError(state.errorMessage);
        this.#updateEmpty(state);
        this.#updateLoading(state);
        this.#updateSentinel(state);
    }

    #configureError(): void {
        this.#error.className = 'chat-attachment-overflow-error';
        this.#error.setAttribute('aria-live', 'polite');
        const retry = dom.getDocument().createElement('button');
        const retryLabel = i18n.t('chat.attachments.modal.retry');
        retry.type = 'button';
        retry.className = 'ui-button ui-variant-neutral';
        retry.dataset['attachmentOverflowAction'] = 'retry';
        retry.setAttribute('aria-label', retryLabel);
        setTooltipText(retry, retryLabel);
        retry.textContent = retryLabel;
        this.#error.append(this.#errorText, retry);
    }

    #configureListNodes(): void {
        this.list.className = LIST_CLASS_NAME;
        this.empty.className = `${EMPTY_CLASS_NAME} ui-empty-state--simple`;
    }

    #configureLoading(): void {
        this.#loading.className = 'chat-attachment-overflow-loading';
        this.#loading.setAttribute('aria-live', 'polite');
        const spinner = dom.getDocument().createElement('span');
        spinner.className = 'loading-spinner';
        spinner.setAttribute('aria-hidden', 'true');
        const text = dom.getDocument().createElement('span');
        text.textContent = i18n.t('chat.attachments.modal.loadingItems');
        this.#loading.append(spinner, text);
        this.sentinel.className = 'chat-attachment-overflow-sentinel';
        this.sentinel.setAttribute('aria-hidden', 'true');
    }

    #updateToolbar(state: AttachmentOverflowModalViewState): void {
        if (!state.knowledgeActive) {
            this.#toolbar.hidden = true;
            this.#toolbar.replaceChildren();
            return;
        }
        const focusedQuery = dom.getDocument().activeElement;
        const existingQuery = dom.resolve('[data-attachment-overflow-control="query"]', this.#toolbar);
        const preserveQuery = existingQuery instanceof HTMLInputElement && focusedQuery === existingQuery ? existingQuery.value : state.query;
        this.#toolbar.hidden = false;
        this.#toolbar.replaceChildren(
            createKnowledgeToolbar({
                statusFilter: state.statusFilter,
                query: preserveQuery,
                loading: state.loadingKnowledge
            })
        );
    }

    #updateError(message: string | null): void {
        this.#error.hidden = message === null;
        this.#errorText.textContent = message ?? '';
    }

    #updateEmpty(state: AttachmentOverflowModalViewState): void {
        const text = resolveEmptyText(state);
        this.empty.textContent = text;
        this.empty.hidden = text.length === 0;
    }

    #updateLoading(state: AttachmentOverflowModalViewState): void {
        this.#loading.hidden = !state.loadingKnowledge;
    }

    #updateSentinel(state: AttachmentOverflowModalViewState): void {
        this.sentinel.hidden = !state.knowledgeActive || !state.hasNextKnowledgePage || state.loadingKnowledge || state.errorMessage !== null;
    }
}

export { AttachmentOverflowModalShell, TOOLBAR_CLASS_NAME };
export type { AttachmentOverflowModalViewState };
