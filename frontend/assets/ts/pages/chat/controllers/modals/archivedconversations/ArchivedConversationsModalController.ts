/* SoAI - Archived conversations modal controller [frontend/assets/ts/pages/chat/controllers/modals/archivedconversations/ArchivedConversationsModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { resolveDelegatedActionElementResult } from '@core/dom/dataAction.ts';
import { ARCHIVED_CONVERSATIONS_MODAL_ID, limitConversationTitleLength } from '@features/chat/public.ts';
import { resolveArchivedConversationsModalRefs } from '@pages/chat/controllers/modals/archivedconversations/ArchivedConversationsRefsModal.ts';
import { isArchivedConversationAction, requireArchivedConversationActionId, resolveArchivedConversationActionErrorMessage } from '@pages/chat/controllers/modals/archivedconversations/actions.ts';
import { loadArchivedConversationsPage, resetArchivedConversationState, searchArchivedConversations } from '@pages/chat/controllers/modals/archivedconversations/pagination/service.ts';
import { renderArchivedConversationsModal } from '@pages/chat/controllers/modals/archivedconversations/view.ts';
import { batchDeleteArchivedConversations, batchUnarchiveConversations, deleteArchivedConversation, saveArchivedConversationRename, startArchivedConversationRename, toggleArchivedConversationFavorite, unarchiveConversation, updateArchivedConversationColor } from '@pages/chat/controllers/modals/archivedconversations/service.ts';
import type { ArchivedConversationAction, ArchivedConversationsModalHost, ArchivedConversationsModalRefs, ArchivedConversationsModalState } from '@pages/chat/controllers/modals/archivedconversations/types.ts';

const SCROLL_LOAD_THRESHOLD_PX = 64;
const SEARCH_DELAY_MS = 180;

class ArchivedConversationsModalController implements EventListenerObject {
    readonly #host: ArchivedConversationsModalHost;
    readonly #timers = new ResourceTracker();
    #abortController: AbortController | null = null;
    #refs: ArchivedConversationsModalRefs | null = null;
    #searchTimer: number | null = null;
    #state: ArchivedConversationsModalState = {
        conversations: [],
        totalCount: 0,
        nextCursor: null,
        query: '',
        loading: false,
        requestVersion: 0,
        searchMode: false,
        selectedIds: new Set(),
        selectionActive: false,
        renamingId: null,
        renameDraft: '',
        colorPickerOpenId: null
    };

    constructor(host: ArchivedConversationsModalHost) {
        this.#host = host;
    }

    async open(): Promise<void> {
        this.dispose();
        const presenter = requireModalPresenter();
        presenter.open(ARCHIVED_CONVERSATIONS_MODAL_ID);
        const root = presenter.requireElement(ARCHIVED_CONVERSATIONS_MODAL_ID);
        const refs = resolveArchivedConversationsModalRefs(root);
        this.#abortController = new AbortController();
        this.#refs = refs;
        this.#bind(refs);
        resetArchivedConversationState(this.#state, '');
        await this.#loadFirstPage(refs);
    }

    dispose(): void {
        if (this.#searchTimer !== null) {
            this.#timers.clearTimeout(this.#searchTimer);
            this.#searchTimer = null;
        }
        this.#abortController?.abort();
        this.#abortController = null;
        this.#refs = null;
    }

    #bind(refs: ArchivedConversationsModalRefs): void {
        const signal = this.#requireSignal();
        refs.root.addEventListener('click', this, { signal });
        refs.root.addEventListener('change', this, { signal });
        refs.root.addEventListener('input', this, { signal });
        refs.root.addEventListener('core.modal.close', this, { signal });
        refs.searchInput.addEventListener('input', this, { signal });
        refs.scrollContainer.addEventListener('scroll', this, { signal });
    }

    #requireSignal(): AbortSignal {
        if (!this.#abortController) {
            throw new Error('Archived conversations modal abort controller is not active');
        }
        return this.#abortController.signal;
    }

    handleEvent(event: Event): void {
        if (!this.#refs) {
            throw new Error('Archived conversations modal refs are not active');
        }
        const refs = this.#refs;
        if (event.type === 'click') this.#handleClick(refs, event);
        else if (event.type === 'change') this.#handleChange(event);
        else if (event.type === 'input' && event.target === refs.searchInput) this.#scheduleSearch(refs);
        else if (event.type === 'input') this.#handleInput(event);
        else if (event.type === 'scroll') this.#handleScroll(refs);
        else if (event.type === 'core.modal.close') this.dispose();
    }

    #syncRenameDraftInput(target: HTMLInputElement): void {
        const draft = limitConversationTitleLength(target.value);
        if (target.value !== draft) {
            target.value = draft;
        }
        this.#state.renameDraft = draft;
    }

    async #loadFirstPage(refs: ArchivedConversationsModalRefs): Promise<void> {
        try {
            await loadArchivedConversationsPage(this.#host, this.#state, this.#requireSignal());
            if (!this.#abortController || this.#abortController.signal.aborted) {
                return;
            }
            renderArchivedConversationsModal(this.#host, refs, this.#state);
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#handleError(runtimeError, i18n.t('chat.archive.errors.loadFailed'));
        }
    }

    #handleClick(refs: ArchivedConversationsModalRefs, event: Event): void {
        const actionResult = resolveDelegatedActionElementResult({
            root: refs.root,
            event,
            preventDefault: 'interactive',
            stopPropagation: true,
            mouseButton: 'primary',
            ignoreDisabled: true
        });
        if (actionResult.type !== 'action') {
            this.#closeColorPickerOnOutsideClick(refs, event);
            return;
        }
        const action = actionResult.actionElement.dataset.action;
        if (!isArchivedConversationAction(action)) {
            throw new Error(`Archived conversations modal received unsupported action ${action}`);
        }
        const item = actionResult.actionElement.closest('.archived-conversation-item');
        const conversationId = requireArchivedConversationActionId(action, item instanceof HTMLElement ? item.dataset['id'] : null);
        void this.#dispatchAction(refs, action, conversationId, actionResult.actionElement).catch((error) => this.#handleError(error, resolveArchivedConversationActionErrorMessage(action)));
    }

    #closeColorPickerOnOutsideClick(refs: ArchivedConversationsModalRefs, event: Event): void {
        if (this.#state.colorPickerOpenId === null) {
            return;
        }
        const target = event.target;
        if (target instanceof Element && target.closest('.chat-conversation-color-picker')) {
            return;
        }
        this.#state.colorPickerOpenId = null;
        this.#renderIfActive(refs);
    }

    async #dispatchAction(refs: ArchivedConversationsModalRefs, action: ArchivedConversationAction, conversationId: string, target: HTMLElement): Promise<void> {
        if (action === 'archive:open-color-picker') {
            this.#state.colorPickerOpenId = this.#state.colorPickerOpenId === conversationId ? null : conversationId;
            this.#renderIfActive(refs);
            return;
        }
        const keepsPickerOpen = action === 'archive:select-color' || action === 'archive:favorite' || (action === 'archive:open' && target.closest('.chat-conversation-color-picker') !== null);
        if (!keepsPickerOpen) {
            this.#state.colorPickerOpenId = null;
        }
        if (action === 'archive:enter-select-mode') this.#state.selectionActive = true;
        else if (action === 'archive:exit-select-mode') {
            this.#state.selectionActive = false;
            this.#state.selectedIds.clear();
        } else if (action === 'archive:select') this.#toggleSelection(conversationId);
        else if (action === 'archive:batch-unarchive') await batchUnarchiveConversations(this.#host, this.#state);
        else if (action === 'archive:batch-delete') await batchDeleteArchivedConversations(this.#host, this.#state);
        else if (action === 'archive:open') this.#handleRowOpen(conversationId, target);
        else if (action === 'archive:unarchive') await unarchiveConversation(this.#host, this.#state, conversationId);
        else if (action === 'archive:delete') await deleteArchivedConversation(this.#host, this.#state, conversationId);
        else if (action === 'archive:favorite') await toggleArchivedConversationFavorite(this.#host, this.#state, conversationId);
        else if (action === 'archive:select-color') await updateArchivedConversationColor(this.#host, this.#state, conversationId, target.dataset['color'] ?? '');
        else if (action === 'archive:rename-start') startArchivedConversationRename(this.#state, conversationId);
        else if (action === 'archive:rename-cancel') this.#cancelRename(conversationId);
        else if (action === 'archive:rename-save') await saveArchivedConversationRename(this.#host, this.#state, conversationId);
        this.#renderIfActive(refs);
    }

    #handleChange(event: Event): void {
        const target = event.target;
        if (!(target instanceof HTMLInputElement)) {
            return;
        }
        if (target.classList.contains('archived-conversation-title-input')) {
            this.#syncRenameDraftInput(target);
        }
    }

    #handleInput(event: Event): void {
        const target = event.target;
        if (target instanceof HTMLInputElement && target.classList.contains('archived-conversation-title-input')) {
            this.#syncRenameDraftInput(target);
        }
    }

    #handleScroll(refs: ArchivedConversationsModalRefs): void {
        const remaining = refs.scrollContainer.scrollHeight - refs.scrollContainer.scrollTop - refs.scrollContainer.clientHeight;
        if (remaining > SCROLL_LOAD_THRESHOLD_PX) {
            return;
        }
        void loadArchivedConversationsPage(this.#host, this.#state, this.#requireSignal())
            .then(() => this.#renderIfActive(refs))
            .catch((error) => this.#handleError(error, i18n.t('chat.archive.errors.loadFailed')));
    }

    #scheduleSearch(refs: ArchivedConversationsModalRefs): void {
        if (this.#searchTimer !== null) this.#timers.clearTimeout(this.#searchTimer);
        this.#searchTimer = this.#timers.setTimeout(() => {
            this.#searchTimer = null;
            const query = toTrimmedString(refs.searchInput.value);
            resetArchivedConversationState(this.#state, query);
            const task = query ? searchArchivedConversations(this.#host, this.#state, this.#requireSignal()) : loadArchivedConversationsPage(this.#host, this.#state, this.#requireSignal());
            void task.then(() => this.#renderIfActive(refs)).catch((error) => this.#handleError(error, i18n.t('chat.archive.errors.loadFailed')));
        }, SEARCH_DELAY_MS);
    }

    #handleRowOpen(conversationId: string, target: HTMLElement): void {
        if (this.#state.selectionActive) {
            this.#toggleSelection(conversationId);
            return;
        }
        if (!target.closest('.archived-conversation-actions')) {
            this.#openConversation(conversationId);
        }
    }

    #toggleSelection(conversationId: string): void {
        if (this.#state.selectedIds.has(conversationId)) {
            this.#state.selectedIds.delete(conversationId);
        } else {
            this.#state.selectedIds.add(conversationId);
        }
    }

    #openConversation(conversationId: string): void {
        this.#host.openConversationEnsuringLoaded(conversationId);
        requireModalPresenter().close(ARCHIVED_CONVERSATIONS_MODAL_ID);
    }

    #cancelRename(conversationId: string): void {
        if (this.#state.renamingId !== conversationId) {
            throw new Error('Archived conversation rename cancel does not match the active rename id');
        }
        this.#state.renamingId = null;
    }

    #renderIfActive(refs: ArchivedConversationsModalRefs): void {
        if (!this.#abortController || this.#abortController.signal.aborted) {
            return;
        }
        renderArchivedConversationsModal(this.#host, refs, this.#state);
    }

    #handleError(error: Error, message: string): void {
        if (isAbortError(error) || !this.#abortController || this.#abortController.signal.aborted) {
            return;
        }
        this.#host.feedback.handle(error, 'Archived conversations action failed');
        this.#host.feedback.show(message, 'error');
    }
}

export { ArchivedConversationsModalController };
