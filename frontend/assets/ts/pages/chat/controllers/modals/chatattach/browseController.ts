/* SoAI - Chat attach modal browse controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/browseController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseFileBrowserLoadResponse } from '@core/fileexplorerbrowser/parsing.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { requireSortableColumn, resolveNextSortState } from '@core/ui/tables/sortableTable.ts';
import { captureSoaiLinkWorkspaceSnapshot, matchesSoaiLinkWorkspaceSnapshot } from '@features/chat/public.ts';
import type { ChatAttachBrowseHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { ChatAttachBrowseWorkspacePathController } from '@pages/chat/controllers/modals/chatattach/ChatAttachBrowseWorkspacePathController.ts';
import { ChatAttachBrowseKnowledgeOperations } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseKnowledgeController.ts';
import { createTrackedBrowseAbortController, releaseTrackedBrowseAbortController, type BrowseAbortControllerRegistry } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseAbortController.ts';
import { renderBrowseResultsTable } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseResultsTableWidget.ts';
import { CHAT_ATTACH_BROWSE_SORT_COLUMN_DEFAULT_DIRECTIONS, CHAT_ATTACH_BROWSE_SORT_COLUMNS, buildWorkspaceBrowseResults, parseReusableKnowledgeResults, sortBrowseResults, type ChatAttachBrowseResult, type ChatAttachBrowseSortState } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseResultsWidget.ts';
import { renderBrowseMessage, setBrowseFooterButtonState } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseStateWidget.ts';
import { ChatAttachBrowseWorkspaceOperations } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseWorkspaceController.ts';
import type { ChatAttachBrowseElements } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseWidget.ts';

const BROWSE_RESULT_LIMIT = 20;

class ChatAttachBrowseController {
    readonly #host: ChatAttachBrowseHost;
    readonly #elements: ChatAttachBrowseElements;
    readonly #knowledgeOperations: ChatAttachBrowseKnowledgeOperations;
    readonly #workspaceOperations: ChatAttachBrowseWorkspaceOperations;
    readonly #workspacePathController: ChatAttachBrowseWorkspacePathController;
    readonly #signal: AbortSignal;
    readonly #searchControllers: BrowseAbortControllerRegistry = new Set();
    #active = false;
    #generation = 0;
    #searchController: AbortController | null = null;
    #results: ChatAttachBrowseResult[] = [];
    #sortState: ChatAttachBrowseSortState = { column: 'name', direction: 'asc' };
    #selectedKey: string | null = null;
    #selectionGeneration = 0;
    #openGeneration = 0;

    constructor(host: ChatAttachBrowseHost, elements: ChatAttachBrowseElements, signal: AbortSignal) {
        this.#host = host;
        this.#elements = elements;
        this.#signal = signal;
        this.#knowledgeOperations = new ChatAttachBrowseKnowledgeOperations(host, signal);
        this.#workspaceOperations = new ChatAttachBrowseWorkspaceOperations(host, signal);
        this.#workspacePathController = new ChatAttachBrowseWorkspacePathController(host, elements, async () => this.#search());
        this.#syncFooter();
    }

    activate(): void {
        this.#active = true;
        this.#workspacePathController.activate();
        this.#syncFooter();
        this.#host.execution.run('chat:attachModalBrowseSearch', () => this.#search());
    }

    deactivate(): void {
        this.#active = false;
        this.#workspacePathController.deactivate();
        this.#selectionGeneration += 1;
        this.#abortBrowseActions();
        this.#abortSearch();
        this.#syncFooter();
    }

    async openWorkspacePathPicker(): Promise<void> {
        await this.#workspacePathController.openPicker();
    }

    handleInput(): void {
        if (!this.#active) {
            return;
        }
        this.#host.execution.run('chat:attachModalBrowseSearchInput', () => this.#search());
    }

    selectResult(resultKey: string | null, actionElement: HTMLElement, event: Event): void {
        if (resultKey === null) {
            return;
        }
        const nextSelectedKey = this.#resolveNextSelectedKey(resultKey, actionElement, event);
        if (this.#selectedKey !== nextSelectedKey) {
            this.#selectionGeneration += 1;
        }
        this.#selectedKey = nextSelectedKey;
        this.#renderResults();
        this.#syncFooter();
    }

    async openResult(resultKey: string | null, actionElement: HTMLElement, event: Event): Promise<void> {
        if (resultKey === null) {
            return;
        }
        if (event instanceof MouseEvent && (event.ctrlKey || event.metaKey)) {
            this.selectResult(resultKey, actionElement, event);
            return;
        }
        const result = this.#resultByKey(resultKey);
        if (result === null) {
            return;
        }
        this.#openGeneration += 1;
        this.#abortBrowseActions();
        const openGeneration = this.#openGeneration;
        const conversationId = this.#currentConversationId();
        if (conversationId === null) {
            return;
        }
        if (result.type === 'workspace') {
            await this.#workspaceOperations.preview(result, () => this.#isCurrentOpen(openGeneration, result.key, conversationId));
            return;
        }
        await this.#knowledgeOperations.preview(result, () => this.#isCurrentOpen(openGeneration, result.key, conversationId));
    }

    sortResults(column: string | null): void {
        if (column === null) {
            return;
        }
        const sortColumn = requireSortableColumn(CHAT_ATTACH_BROWSE_SORT_COLUMNS, column, 'chat attach browse');
        this.#sortState = resolveNextSortState(this.#sortState, sortColumn, CHAT_ATTACH_BROWSE_SORT_COLUMN_DEFAULT_DIRECTIONS[sortColumn]);
        this.#renderResults();
    }

    async previewSelected(): Promise<void> {
        const selected = this.#selectedResult();
        if (selected === null) {
            return;
        }
        const selectionGeneration = this.#selectionGeneration;
        const conversationId = this.#currentConversationId();
        if (conversationId === null) {
            return;
        }
        this.#abortBrowseActions();
        if (selected.type === 'workspace') {
            await this.#workspaceOperations.preview(selected, () => this.#isCurrentSelection(selectionGeneration, selected.key, conversationId));
            return;
        }
        await this.#knowledgeOperations.preview(selected, () => this.#isCurrentSelection(selectionGeneration, selected.key, conversationId));
    }

    async attachSelected(): Promise<boolean> {
        const selected = this.#selectedResult();
        if (selected === null) {
            return false;
        }
        const selectionGeneration = this.#selectionGeneration;
        const conversationId = this.#currentConversationId();
        if (conversationId === null) {
            return false;
        }
        this.#abortBrowseActions();
        if (selected.type === 'workspace') {
            return await this.#workspaceOperations.attach(selected, () => this.#isCurrentSelection(selectionGeneration, selected.key, conversationId));
        }
        return await this.#knowledgeOperations.attach(selected, () => this.#isCurrentSelection(selectionGeneration, selected.key, conversationId));
    }

    #abortBrowseActions(): void {
        this.#workspaceOperations.abortPending();
        this.#knowledgeOperations.abortPending();
    }

    #abortSearch(): void {
        const controller = this.#searchController;
        this.#searchController = null;
        if (controller !== null) {
            releaseTrackedBrowseAbortController(this.#searchControllers, controller);
        }
    }

    #selectedResult(): ChatAttachBrowseResult | null {
        const key = this.#selectedKey;
        if (key === null) {
            return null;
        }
        return this.#resultByKey(key);
    }

    #resultByKey(key: string): ChatAttachBrowseResult | null {
        return this.#results.find((result) => result.key === key) ?? null;
    }

    #syncFooter(): void {
        const enabled = this.#selectedResult() !== null;
        setBrowseFooterButtonState(this.#elements.previewButton, this.#active, enabled);
        setBrowseFooterButtonState(this.#elements.attachButton, this.#active, enabled);
    }

    #renderResults(): void {
        renderBrowseResultsTable(this.#elements.results, sortBrowseResults(this.#results, this.#sortState), this.#selectedKey, this.#sortState);
    }

    async #search(): Promise<void> {
        this.#abortSearch();
        this.#generation += 1;
        const generation = this.#generation;
        const controller = createTrackedBrowseAbortController(this.#searchControllers, this.#signal);
        this.#searchController = controller;
        renderBrowseMessage(this.#elements.results, i18n.t('chat.attachModal.browseLoadingTitle'), i18n.t('chat.attachModal.browseLoadingSubtitle'), true);
        try {
            const query = this.#elements.searchInput.value.trim();
            const conversation = this.#host.conversation.current();
            const conversationId = toTrimmedStringOrNull(conversation?.id);
            if (conversationId === null) {
                if (this.#selectedKey !== null) {
                    this.#selectionGeneration += 1;
                }
                this.#results = [];
                this.#selectedKey = null;
                renderBrowseMessage(this.#elements.results, i18n.t('chat.attachModal.browseNeedsConversation'), i18n.t('chat.attachModal.browseEmptySubtitle'));
                this.#syncFooter();
                return;
            }
            const workspaceSnapshot = captureSoaiLinkWorkspaceSnapshot(conversation);
            const workspaceRequest = this.#host.shared.api.webui.chat.soaiPaths.browse(conversationId, { query: query || null, limit: BROWSE_RESULT_LIMIT }, { signal: controller.signal });
            const knowledgeRequest = this.#host.shared.api.webui.chat.attachments.knowledge.reusable({ query: query || undefined, limit: BROWSE_RESULT_LIMIT, signal: controller.signal });
            const [workspacePayload, knowledgePayload] = await Promise.all([workspaceRequest, knowledgeRequest]);
            if (!this.#isCurrent(generation, controller.signal)) {
                return;
            }
            if (!matchesSoaiLinkWorkspaceSnapshot(this.#host.conversation.current(), workspaceSnapshot)) {
                this.#host.execution.run('chat:attachModalBrowseSearchWorkspaceRefresh', () => this.#search());
                return;
            }
            this.#results = [...buildWorkspaceBrowseResults(parseFileBrowserLoadResponse(workspacePayload, query).entries), ...parseReusableKnowledgeResults(knowledgePayload)];
            const nextSelectedKey = this.#results.some((result) => result.key === this.#selectedKey) ? this.#selectedKey : null;
            if (nextSelectedKey !== this.#selectedKey) {
                this.#selectionGeneration += 1;
            }
            this.#selectedKey = nextSelectedKey;
            this.#renderResults();
            this.#syncFooter();
        } catch (error) {
            if (controller.signal.aborted || isAbortError(error)) {
                return;
            }
            throw ensureError(error);
        } finally {
            if (this.#searchController === controller) {
                this.#searchController = null;
            }
            releaseTrackedBrowseAbortController(this.#searchControllers, controller);
        }
    }

    #isCurrent(generation: number, signal: AbortSignal): boolean {
        return this.#active && !this.#signal.aborted && !signal.aborted && generation === this.#generation;
    }

    #currentConversationId(): string | null {
        return toTrimmedStringOrNull(this.#host.conversation.currentId());
    }

    #isCurrentSelection(selectionGeneration: number, resultKey: string, conversationId: string): boolean {
        return this.#active && !this.#signal.aborted && selectionGeneration === this.#selectionGeneration && this.#selectedKey === resultKey && this.#currentConversationId() === conversationId;
    }

    #isCurrentOpen(openGeneration: number, resultKey: string, conversationId: string): boolean {
        return this.#active && !this.#signal.aborted && openGeneration === this.#openGeneration && this.#resultByKey(resultKey) !== null && this.#currentConversationId() === conversationId;
    }

    #resolveNextSelectedKey(resultKey: string, actionElement: HTMLElement, event: Event): string | null {
        const checkboxToggled = actionElement instanceof HTMLInputElement && actionElement.type === 'checkbox';
        const modifierToggled = event instanceof MouseEvent && (event.ctrlKey || event.metaKey);
        if ((checkboxToggled || modifierToggled) && this.#selectedKey === resultKey) {
            return null;
        }
        return resultKey;
    }
}

export { ChatAttachBrowseController };
export type { ChatAttachBrowseElements };
